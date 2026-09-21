import { afterEach, describe, expect, it, vi } from 'vitest';
import * as httpClient from './httpClient';
import { API_BASE_URL } from './httpClient';
import { isTerminalTtsJobStatus, ttsJobService } from './ttsJobService';
import type { TtsJob } from './ttsJobService';

const API_ORIGIN = new URL(API_BASE_URL).origin;

describe('ttsJobService', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('submit() POSTs to /tts/jobs with the given payload and signal', async () => {
    const apiFetchSpy = vi
      .spyOn(httpClient, 'apiFetch')
      .mockResolvedValueOnce({ job_id: 'j1', status: 'QUEUED' } satisfies TtsJob);
    const controller = new AbortController();

    const result = await ttsJobService.submit(
      { text: 'hi', source_language: 'vi', language: 'vi', speed: 1.0, format: 'wav', idempotency_key: 'abc' },
      controller.signal
    );

    expect(result).toEqual({ job_id: 'j1', status: 'QUEUED' });
    expect(apiFetchSpy).toHaveBeenCalledWith('/tts/jobs', {
      method: 'POST',
      body: { text: 'hi', source_language: 'vi', language: 'vi', speed: 1.0, format: 'wav', idempotency_key: 'abc' },
      signal: controller.signal,
    });
  });

  it('get() GETs /tts/jobs/{id} with the id URL-encoded', async () => {
    const apiFetchSpy = vi
      .spyOn(httpClient, 'apiFetch')
      .mockResolvedValueOnce({ job_id: 'a/b', status: 'RUNNING' } satisfies TtsJob);

    const result = await ttsJobService.get('a/b');

    expect(result.status).toBe('RUNNING');
    expect(apiFetchSpy).toHaveBeenCalledWith('/tts/jobs/a%2Fb', { signal: undefined });
  });

  it('list() GETs /tts/jobs and returns the array as-is', async () => {
    const jobs: TtsJob[] = [
      { job_id: 'j1', status: 'COMPLETED' },
      { job_id: 'j2', status: 'FAILED' },
    ];
    const apiFetchSpy = vi.spyOn(httpClient, 'apiFetch').mockResolvedValueOnce(jobs);

    const result = await ttsJobService.list();

    expect(result).toBe(jobs);
    expect(apiFetchSpy).toHaveBeenCalledWith('/tts/jobs', { signal: undefined });
  });

  it('resolveAudioUrl() qualifies a backend-relative audio_url and returns null when absent', () => {
    const resolved = ttsJobService.resolveAudioUrl({ audio_url: '/api/audio/xyz.wav' });
    expect(resolved).toBe(`${API_ORIGIN}/api/audio/xyz.wav`);

    expect(ttsJobService.resolveAudioUrl({ audio_url: null })).toBeNull();
    expect(ttsJobService.resolveAudioUrl({ audio_url: undefined })).toBeNull();
  });

  it('guessFormat() infers wav/mp3 from the audio_url extension, or null when unknown/absent', () => {
    expect(ttsJobService.guessFormat({ audio_url: '/api/audio/x.wav' })).toBe('wav');
    expect(ttsJobService.guessFormat({ audio_url: '/api/audio/x.mp3' })).toBe('mp3');
    expect(ttsJobService.guessFormat({ audio_url: '/api/audio/x.ogg' })).toBeNull();
    expect(ttsJobService.guessFormat({ audio_url: null })).toBeNull();
  });

  it('isTerminalTtsJobStatus() is true only for COMPLETED/FAILED', () => {
    expect(isTerminalTtsJobStatus('QUEUED')).toBe(false);
    expect(isTerminalTtsJobStatus('RUNNING')).toBe(false);
    expect(isTerminalTtsJobStatus('COMPLETED')).toBe(true);
    expect(isTerminalTtsJobStatus('FAILED')).toBe(true);
  });
});
