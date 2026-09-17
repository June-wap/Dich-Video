import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { apiFetch, ApiError, NetworkError, resolveBackendUrl, API_BASE_URL } from './httpClient';

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

describe('apiFetch', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('returns parsed JSON on a 2xx response', async () => {
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce(jsonResponse(200, { hello: 'world' }));

    const data = await apiFetch<{ hello: string }>('/ping');

    expect(data).toEqual({ hello: 'world' });
    expect(fetch).toHaveBeenCalledWith(
      `${API_BASE_URL}/ping`,
      expect.objectContaining({ body: undefined })
    );
  });

  it('sends a JSON body and Content-Type header for object bodies', async () => {
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce(jsonResponse(202, { ok: true }));

    await apiFetch('/tts/jobs', { method: 'POST', body: { text: 'hi' } });

    const [, init] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(init.method).toBe('POST');
    expect(init.body).toBe(JSON.stringify({ text: 'hi' }));
    expect(init.headers['Content-Type']).toBe('application/json');
  });

  it('throws ApiError with the backend error envelope on a non-2xx response', async () => {
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      jsonResponse(409, { ok: false, error: { code: 'IDEMPOTENCY_KEY_CONFLICT', message: 'Conflict' } })
    );

    const promise = apiFetch('/tts/jobs', { method: 'POST', body: {} });
    await expect(promise).rejects.toBeInstanceOf(ApiError);
    await expect(promise).rejects.toMatchObject({
      code: 'IDEMPOTENCY_KEY_CONFLICT',
      status: 409,
      message: 'Conflict',
    });
  });

  it('throws NetworkError when fetch itself fails (offline/CORS/backend down)', async () => {
    (fetch as ReturnType<typeof vi.fn>).mockRejectedValueOnce(new TypeError('Failed to fetch'));

    await expect(apiFetch('/tts/jobs')).rejects.toBeInstanceOf(NetworkError);
  });

  it('re-throws AbortError as-is so callers can distinguish cancellation', async () => {
    const abortError = new DOMException('Aborted', 'AbortError');
    (fetch as ReturnType<typeof vi.fn>).mockRejectedValueOnce(abortError);

    await expect(apiFetch('/tts/jobs')).rejects.toBe(abortError);
  });
});

describe('resolveBackendUrl', () => {
  it('prefixes a backend-relative path with the API origin', () => {
    expect(resolveBackendUrl('/api/audio/abc.wav')).toBe(`${new URL(API_BASE_URL).origin}/api/audio/abc.wav`);
  });

  it('passes an already-absolute URL through unchanged', () => {
    expect(resolveBackendUrl('https://example.com/x.wav')).toBe('https://example.com/x.wav');
  });
});
