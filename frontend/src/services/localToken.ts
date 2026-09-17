/**
 * Local API auth token bootstrap (security P0 - see the project's
 * checklist-bao-mat-truoc-dong-goi-17-09.md item 1). backend/main.py
 * generates a fresh random token every time the backend process starts and
 * requires every other request to present it (X-Local-Token header, or a
 * `token` query parameter for the two request kinds that cannot set a
 * custom header - see resolveBackendUrl in ./httpClient.ts). Since the
 * frontend has no way to already know a value the backend only just
 * generated, it fetches it once from GET /api/auth/token
 * (backend/api/auth.py) - the one endpoint the backend's own middleware
 * exempts from already needing the token, gated instead on this page's
 * Origin header matching an allowed CORS origin (backend and frontend
 * always run on different ports/origins here, so the browser always
 * attaches a real, unspoofable Origin header to this cross-origin fetch).
 *
 * Deliberately does not import from ./httpClient (which needs to import
 * getLocalToken from here to attach the header on every other call) - that
 * would be a circular module import. The tiny bit of URL-building
 * duplicated below is the trade-off for avoiding that.
 */

const AUTH_TOKEN_URL: string =
  ((import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/+$/, '') ||
    'http://127.0.0.1:8000/api') + '/auth/token';

// Vitest sets import.meta.env.TEST. Every existing unit test either mocks
// apiFetch entirely or stubs the global fetch itself (see httpClient.test.ts),
// so a real network round-trip here would just race/pollute those mocks (and,
// if the backend truly isn't running, retry for ~10s per test). No test
// asserts on the token value or this header's presence, so a fixed stand-in
// is enough - kept separate from getCachedLocalToken() below, which
// deliberately stays null in tests instead, so existing exact-URL
// assertions (resolveBackendUrl/resolveAudioUrl) are unaffected.
const IS_TEST_ENV = Boolean(import.meta.env.TEST);
const TEST_TOKEN = 'vitest-local-token';

let cachedToken: string | null = null;
let tokenPromise: Promise<string> | null = null;

async function fetchToken(): Promise<string> {
  // The frontend and backend are started as two separate processes with no
  // ordering enforced in code (see huong-dan-chay-chuong-trinh.md) - retry
  // for a few seconds in case this page loads before the backend has
  // finished starting, rather than failing the whole app on that race.
  const attempts = 40;
  let lastError: unknown;
  for (let attempt = 0; attempt < attempts; attempt++) {
    try {
      const response = await fetch(AUTH_TOKEN_URL);
      if (response.ok) {
        const data = (await response.json()) as { token?: string };
        if (data.token) {
          cachedToken = data.token;
          return data.token;
        }
      }
    } catch (err) {
      lastError = err;
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error(
    'Không thể lấy mã xác thực cục bộ từ backend (GET /api/auth/token). ' +
      'Hãy đảm bảo backend đang chạy (xem hướng dẫn chạy chương trình) rồi tải lại trang.',
    { cause: lastError },
  );
}

/** Resolves once the token is available; safe to call from many places -
 * only the very first caller actually triggers a network request. */
export function getLocalToken(): Promise<string> {
  if (IS_TEST_ENV) return Promise.resolve(TEST_TOKEN);
  if (cachedToken) return Promise.resolve(cachedToken);
  if (!tokenPromise) tokenPromise = fetchToken();
  return tokenPromise;
}

/** Synchronous, cache-only read for render-time URL building
 * (resolveBackendUrl in ./httpClient.ts). Returns null until getLocalToken()
 * has resolved at least once - main.tsx awaits it before the app's first
 * render, so every component render after that is guaranteed a real value
 * here. Always null in tests (see IS_TEST_ENV above): nothing in this
 * module populates `cachedToken` in test mode, which is deliberate - it
 * keeps existing exact-URL assertions in ttsJobService.test.ts/
 * TTSPage.test.tsx unaffected. */
export function getCachedLocalToken(): string | null {
  return cachedToken;
}
