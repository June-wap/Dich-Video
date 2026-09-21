/**
 * Real API client for the persisted Short TTS Job API (Task 2 / backend
 * routes registered in backend/api/tts_jobs.py). Mirrors the backend's
 * TTSStatus/TTSRequest schemas (backend/schemas/tts.py) field-for-field -
 * this file intentionally does NOT reuse the older `TTSRequest`/`TTSResult`
 * mock types in ./types.ts, which model a different (unimplemented) shape
 * and are not read by any current page.
 */
import { apiFetch, resolveBackendUrl } from './httpClient';

export type TtsJobStatus = 'QUEUED' | 'RUNNING' | 'COMPLETED' | 'FAILED';

export interface TtsJobErrorBody {
  code: string;
  message: string;
}

/** Matches backend TTSStatus exactly: job_id, status, audio_url, error. The
 * backend intentionally does not return text/voice/timestamps for a job -
 * see the "known limitations" note in the Task 3 report. */
export interface TtsJob {
  job_id: string;
  status: TtsJobStatus;
  audio_url?: string | null;
  error?: TtsJobErrorBody | null;
}

export type TtsAudioFormat = 'wav' | 'mp3';

export interface SubmitTtsJobPayload {
  text: string;
  source_language: string;
  language: string;
  voice_id?: string | null;
  speed: number;
  format: TtsAudioFormat;
  idempotency_key?: string | null;
}

export const ttsJobService = {
  /** POST /api/tts/jobs -> 202 TtsJob (status QUEUED, or an existing job's
   * current status when idempotency_key matches a prior identical request). */
  submit(payload: SubmitTtsJobPayload, signal?: AbortSignal): Promise<TtsJob> {
    return apiFetch<TtsJob>('/tts/jobs', { method: 'POST', body: payload, signal });
  },

  /** GET /api/tts/jobs/{job_id} -> TtsJob. Throws ApiError(JOB_NOT_FOUND) for
   * an unknown id. */
  get(jobId: string, signal?: AbortSignal): Promise<TtsJob> {
    return apiFetch<TtsJob>(`/tts/jobs/${encodeURIComponent(jobId)}`, { signal });
  },

  /** GET /api/tts/jobs -> persisted job history, oldest first (as returned
   * by the backend; callers reverse for a newest-first display). */
  list(signal?: AbortSignal): Promise<TtsJob[]> {
    return apiFetch<TtsJob[]>('/tts/jobs', { signal });
  },

  /** Turn a job's backend-relative audio_url into a fetchable absolute URL.
   * Never reconstructs the artifact id/path - only qualifies the origin. */
  resolveAudioUrl(job: Pick<TtsJob, 'audio_url'>): string | null {
    return job.audio_url ? resolveBackendUrl(job.audio_url) : null;
  },

  /** Best-effort format guess from audio_url's extension, for display only
   * (the backend does not echo back the requested format on TtsJob). */
  guessFormat(job: Pick<TtsJob, 'audio_url'>): TtsAudioFormat | null {
    if (!job.audio_url) return null;
    if (job.audio_url.endsWith('.mp3')) return 'mp3';
    if (job.audio_url.endsWith('.wav')) return 'wav';
    return null;
  },
};

export const TERMINAL_TTS_JOB_STATUSES: readonly TtsJobStatus[] = ['COMPLETED', 'FAILED'];

export function isTerminalTtsJobStatus(status: TtsJobStatus): boolean {
  return TERMINAL_TTS_JOB_STATUSES.includes(status);
}
