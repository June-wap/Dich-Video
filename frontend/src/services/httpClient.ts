/**
 * Minimal fetch wrapper for the local backend (see backend/README.md).
 *
 * The backend binds to 127.0.0.1 and is a separate origin from the Vite dev
 * server (no dev proxy is configured), so every request needs an absolute
 * base URL. All backend error responses share one envelope:
 *   { "ok": false, "error": { "code": "SOME_CODE", "message": "..." } }
 * (backend/errors/handlers.py). ApiError carries that code/message/status so
 * callers can branch on `code` (e.g. IDEMPOTENCY_KEY_CONFLICT, JOB_NOT_FOUND)
 * instead of parsing message strings.
 *
 * Every request also carries the local API auth token (security P0 - see
 * ./localToken.ts) - the backend rejects anything else with 401 UNAUTHORIZED
 * once Settings.require_local_token is on (every real run - see
 * scripts/run_backend.ps1 - though not most test fixtures).
 */
import { getCachedLocalToken, getLocalToken } from './localToken';

const DEFAULT_API_BASE_URL = 'http://127.0.0.1:8000/api';

export const API_BASE_URL: string =
  (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/+$/, '') ||
  DEFAULT_API_BASE_URL;

/** Origin the API is served from (e.g. http://127.0.0.1:8000), derived from
 * API_BASE_URL rather than hard-coded again, so audio_url values returned by
 * the backend (already-absolute paths like "/api/audio/xxx.wav") resolve to
 * the right host without reconstructing the path ourselves. */
const API_ORIGIN: string = new URL(API_BASE_URL).origin;

export class ApiError extends Error {
  code: string;
  status: number;

  constructor(code: string, message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
    this.status = status;
  }
}

/** Request never reached the server: offline, DNS failure, CORS rejection,
 * backend not running, aborted, etc. Distinct from ApiError (a real HTTP
 * error response) so callers can offer a "check connection" message instead
 * of a validation-style error. */
export class NetworkError extends Error {
  cause?: unknown;

  constructor(
    message = 'Không thể kết nối dịch vụ Voca Basic cục bộ (127.0.0.1:8000). Vui lòng kiểm tra hoặc khởi động lại ứng dụng.',
    cause?: unknown
  ) {
    super(message);
    this.name = 'NetworkError';
    this.cause = cause;
  }
}

interface BackendErrorEnvelope {
  ok: false;
  error: { code: string; message: string };
}

function isBackendErrorEnvelope(value: unknown): value is BackendErrorEnvelope {
  return (
    typeof value === 'object' &&
    value !== null &&
    'error' in value &&
    typeof (value as { error?: unknown }).error === 'object'
  );
}

export interface ApiFetchOptions extends Omit<RequestInit, 'body'> {
  body?: unknown;
}

/**
 * Fetch JSON from the backend. Throws ApiError for non-2xx HTTP responses
 * (using the backend's structured error envelope) and NetworkError when the
 * request could not be made at all (including AbortError, which callers
 * that pass their own AbortSignal will usually want to swallow instead).
 *
 * `body` is normally JSON-serialized with a `Content-Type: application/json`
 * header, as before. A `FormData` body (Task 4: voice-profile reference
 * audio upload, backend/api/voices.py's multipart `POST /voices/profiles`)
 * is passed through to `fetch` unchanged and untouched - `JSON.stringify`
 * would corrupt the file payload, and setting Content-Type ourselves would
 * drop the multipart boundary the browser generates.
 */
export async function apiFetch<T>(path: string, options: ApiFetchOptions = {}): Promise<T> {
  const { body, headers, ...rest } = options;
  const url = `${API_BASE_URL}${path.startsWith('/') ? path : `/${path}`}`;
  const isFormData = typeof FormData !== 'undefined' && body instanceof FormData;

  let token: string;
  try {
    token = await getLocalToken();
  } catch (err) {
    throw new NetworkError('Không thể lấy mã xác thực cục bộ để gọi backend.', err);
  }

  let response: Response;
  try {
    response = await fetch(url, {
      ...rest,
      headers: {
        ...(body !== undefined && !isFormData ? { 'Content-Type': 'application/json' } : {}),
        'X-Local-Token': token,
        ...headers,
      },
      body: body === undefined ? undefined : isFormData ? (body as FormData) : JSON.stringify(body),
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw err; // let callers distinguish deliberate cancellation from real failures
    }
    throw new NetworkError(undefined, err);
  }

  // 204/empty bodies are not used by this API today, but guard defensively.
  const text = await response.text();
  const data: unknown = text ? JSON.parse(text) : undefined;

  if (!response.ok) {
    if (isBackendErrorEnvelope(data)) {
      throw new ApiError(data.error.code, data.error.message, response.status);
    }
    throw new ApiError('UNKNOWN_ERROR', `Yêu cầu thất bại (HTTP ${response.status}).`, response.status);
  }

  return data as T;
}

/** Resolve a backend-provided path (e.g. "/api/audio/xxx.wav") to a fully
 * qualified, fetchable URL. Never reconstructs the path itself - only
 * prefixes it with the backend's own origin, which is required because the
 * frontend and backend run on different ports/origins in dev. */
export function resolveBackendUrl(pathOrUrl: string): string {
  if (/^https?:\/\//i.test(pathOrUrl)) return pathOrUrl;
  const base = `${API_ORIGIN}${pathOrUrl.startsWith('/') ? pathOrUrl : `/${pathOrUrl}`}`;
  // <audio src>/<a download> (AudioPlayer.tsx's RealAudioPlayer) issue plain
  // GET requests the browser builds itself - there is no way to attach a
  // custom X-Local-Token header to those, so the local auth token (see
  // ./localToken.ts) rides along as a query parameter here instead. Omitted
  // entirely when no token is cached yet - always the case in unit tests
  // (see getCachedLocalToken's docstring) - which keeps this a no-op for
  // every caller that never triggered the real bootstrap fetch.
  const token = getCachedLocalToken();
  if (!token) return base;
  return `${base}${base.includes('?') ? '&' : '?'}token=${encodeURIComponent(token)}`;
}
