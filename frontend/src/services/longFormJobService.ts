/**
 * Real API client for the persisted Long-form TTS Job API (Task 4 / backend
 * routes registered in backend/api/long_form.py). Mirrors the backend's
 * LongFormStatus/LongFormRequest schemas (backend/schemas/long_form.py)
 * field-for-field.
 *
 * Unlike Short TTS's job API (ttsJobService.ts), there is:
 *  - no GET /api/tts/long-form list/history endpoint - a real backend
 *    contract limitation, not something to work around client-side;
 *  - no idempotency_key on submit;
 *  - a real, backend-computed progress_percent on every status response;
 *  - a DELETE (cancel) endpoint that returns the job's current status,
 *    which may still be RUNNING if cancellation had not taken effect yet
 *    (the backend only checks for cancellation between chunks) - callers
 *    must keep polling after cancel() until the status is actually terminal.
 */
import { apiFetch, resolveBackendUrl } from './httpClient';

export type LongFormJobStatus = 'QUEUED' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'CANCELLED';

export interface LongFormJobErrorBody {
  code: string;
  message: string;
}

/** Matches backend LongFormStatus exactly. The backend serializes with
 * response_model_exclude_none=True, so audio_url/error are simply absent
 * (not null) on responses where they don't apply - both are modeled as
 * optional here to cover that. */
export interface LongFormJob {
  job_id: string;
  status: LongFormJobStatus;
  progress_percent: number;
  audio_url?: string | null;
  error?: LongFormJobErrorBody | null;
}

export type LongFormAudioFormat = 'wav' | 'mp3';

export interface SubmitLongFormJobPayload {
  text: string;
  language: string;
  /** Required - Long-form has no "default voice" concept like Short TTS's
   * a provider-specific default; every job runs against a real voice-clone profile. */
  profile_id: string;
  format: LongFormAudioFormat;
}

export const longFormJobService = {
  /** POST /api/tts/long-form -> 202 LongFormStatus (status QUEUED). Payload
   * must be exactly {text, language, profile_id, speed, format} -
   * LongFormRequest has model_config = ConfigDict(extra="forbid"), so any
   * extra field (e.g. an idempotency_key) is rejected outright. `speed` is
   * not exposed as a caller param: the backend only accepts exactly 1.0
   * (INVALID_SPEED otherwise). */
  submit(payload: SubmitLongFormJobPayload, signal?: AbortSignal): Promise<LongFormJob> {
    return apiFetch<LongFormJob>('/tts/long-form', {
      method: 'POST',
      body: {
        text: payload.text,
        language: payload.language,
        profile_id: payload.profile_id,
        speed: 1.0,
        format: payload.format,
      },
      signal,
    });
  },

  /** GET /api/tts/long-form/{job_id} -> LongFormStatus. Throws
   * ApiError(JOB_NOT_FOUND) for an unknown id. */
  get(jobId: string, signal?: AbortSignal): Promise<LongFormJob> {
    return apiFetch<LongFormJob>(`/tts/long-form/${encodeURIComponent(jobId)}`, { signal });
  },

  /** DELETE /api/tts/long-form/{job_id} -> the job's current LongFormStatus.
   * A 200 here does NOT guarantee status is CANCELLED yet - see the module
   * doc comment. Callers should feed this response back into their normal
   * polling loop rather than treating it as terminal on its own. */
  cancel(jobId: string, signal?: AbortSignal): Promise<LongFormJob> {
    return apiFetch<LongFormJob>(`/tts/long-form/${encodeURIComponent(jobId)}`, {
      method: 'DELETE',
      signal,
    });
  },

  /** Turn a job's backend-relative audio_url into a fetchable absolute URL.
   * Never reconstructs the artifact id/path - only qualifies the origin. */
  resolveAudioUrl(job: Pick<LongFormJob, 'audio_url'>): string | null {
    return job.audio_url ? resolveBackendUrl(job.audio_url) : null;
  },

  /** Best-effort format guess from audio_url's extension, for display only
   * (the backend does not echo back the requested format on LongFormStatus). */
  guessFormat(job: Pick<LongFormJob, 'audio_url'>): LongFormAudioFormat | null {
    if (!job.audio_url) return null;
    if (job.audio_url.endsWith('.mp3')) return 'mp3';
    if (job.audio_url.endsWith('.wav')) return 'wav';
    return null;
  },
};

export const TERMINAL_LONG_FORM_JOB_STATUSES: readonly LongFormJobStatus[] = [
  'COMPLETED',
  'FAILED',
  'CANCELLED',
];

export function isTerminalLongFormJobStatus(status: LongFormJobStatus): boolean {
  return TERMINAL_LONG_FORM_JOB_STATUSES.includes(status);
}
