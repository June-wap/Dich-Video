import { afterEach, describe, expect, it, vi } from 'vitest';
import * as httpClient from './httpClient';
import { API_BASE_URL } from './httpClient';
import { isTerminalLongFormJobStatus, longFormJobService } from './longFormJobService';
import type { LongFormJob } from './longFormJobService';

const API_ORIGIN = new URL(API_BASE_URL).origin;

describe('longFormJobService', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('submit() POSTs to /tts/long-form with EXACTLY the LongFormRequest shape (speed hardcoded to 1.0)', async () => {
    const apiFetchSpy = vi.spyOn(httpClient, 'apiFetch').mockResolvedValueOnce({
      job_id: 'j1',
      status: 'QUEUED',
      progress_percent: 0,
    } satisfies LongFormJob);
    const controller = new AbortController();

    const result = await longFormJobService.submit(
      { text: 'noi dung dai', language: 'vi', profile_id: 'p1', format: 'wav' },
      controller.signal
    );

    expect(result.status).toBe('QUEUED');
    // Payload must be exactly {text, language, profile_id, speed, format} -
    // LongFormRequest has extra="forbid", so any additional field (e.g. an
    // idempotency_key, unlike Short TTS) would be rejected by the backend.
    expect(apiFetchSpy).toHaveBeenCalledWith('/tts/long-form', {
      method: 'POST',
      body: { text: 'noi dung dai', language: 'vi', profile_id: 'p1', speed: 1.0, format: 'wav' },
      signal: controller.signal,
    });
  });

  it('get() GETs /tts/long-form/{id} with the id URL-encoded', async () => {
    const apiFetchSpy = vi.spyOn(httpClient, 'apiFetch').mockResolvedValueOnce({
      job_id: 'a/b',
      status: 'RUNNING',
      progress_percent: 42,
    } satisfies LongFormJob);

    const result = await longFormJobService.get('a/b');

    expect(result.progress_percent).toBe(42);
    expect(apiFetchSpy).toHaveBeenCalledWith('/tts/long-form/a%2Fb', { signal: undefined });
  });

  it('cancel() DELETEs /tts/long-form/{id} and returns whatever status the backend reports (may still be RUNNING)', async () => {
    const apiFetchSpy = vi.spyOn(httpClient, 'apiFetch').mockResolvedValueOnce({
      job_id: 'j1',
      status: 'RUNNING', // cancellation had not taken effect yet - only checked between chunks
      progress_percent: 55,
    } satisfies LongFormJob);

    const result = await longFormJobService.cancel('j1');

    expect(result.status).toBe('RUNNING');
    expect(apiFetchSpy).toHaveBeenCalledWith('/tts/long-form/j1', { method: 'DELETE', signal: undefined });
  });

  it('resolveAudioUrl() qualifies a backend-relative audio_url and returns null when absent', () => {
    const resolved = longFormJobService.resolveAudioUrl({ audio_url: '/api/audio/xyz.wav' });
    expect(resolved).toBe(`${API_ORIGIN}/api/audio/xyz.wav`);

    expect(longFormJobService.resolveAudioUrl({ audio_url: null })).toBeNull();
    expect(longFormJobService.resolveAudioUrl({ audio_url: undefined })).toBeNull();
  });

  it('guessFormat() infers wav/mp3 from the audio_url extension, or null when unknown/absent', () => {
    expect(longFormJobService.guessFormat({ audio_url: '/api/audio/x.wav' })).toBe('wav');
    expect(longFormJobService.guessFormat({ audio_url: '/api/audio/x.mp3' })).toBe('mp3');
    expect(longFormJobService.guessFormat({ audio_url: '/api/audio/x.ogg' })).toBeNull();
    expect(longFormJobService.guessFormat({ audio_url: null })).toBeNull();
  });

  it('isTerminalLongFormJobStatus() is true only for COMPLETED/FAILED/CANCELLED', () => {
    expect(isTerminalLongFormJobStatus('QUEUED')).toBe(false);
    expect(isTerminalLongFormJobStatus('RUNNING')).toBe(false);
    expect(isTerminalLongFormJobStatus('COMPLETED')).toBe(true);
    expect(isTerminalLongFormJobStatus('FAILED')).toBe(true);
    expect(isTerminalLongFormJobStatus('CANCELLED')).toBe(true);
  });
});
