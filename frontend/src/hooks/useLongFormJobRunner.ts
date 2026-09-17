import { useCallback, useEffect, useRef, useState } from 'react';
import {
  longFormJobService,
  isTerminalLongFormJobStatus,
  type LongFormJob,
  type LongFormAudioFormat,
} from '../services/longFormJobService';
import { ApiError, NetworkError } from '../services/httpClient';

const POLL_INTERVAL_MS = 1000;
const MAX_CONSECUTIVE_POLL_FAILURES = 5;

export interface LongFormFormPayload {
  text: string;
  language: string;
  profileId: string;
  format: LongFormAudioFormat;
}

export type LongFormRunnerPhase = 'idle' | 'submitting' | 'polling' | 'cancelling';

export interface LongFormRunnerError {
  code?: string;
  message: string;
}

export interface UseLongFormJobRunnerResult {
  job: LongFormJob | null;
  phase: LongFormRunnerPhase;
  requestError: LongFormRunnerError | null;
  /** True while a submit/cancel is in flight or an active job is being
   * polled - drives the Submit button's disabled/loading state. */
  isBusy: boolean;
  submit: (payload: LongFormFormPayload) => Promise<void>;
  /**
   * Calls DELETE /api/tts/long-form/{job_id}. The backend only checks for
   * cancellation between chunks, so the response may still report RUNNING -
   * this does NOT treat that as terminal; it feeds the response back into
   * the same polling loop (same generation) so the caller keeps watching
   * until the job actually reaches CANCELLED (or finishes first).
   */
  cancel: () => Promise<void>;
  canCancel: boolean;
  /** The payload that produced the current `job` (or was last attempted). */
  lastPayload: LongFormFormPayload | null;
}

function describeError(err: unknown): LongFormRunnerError {
  if (err instanceof ApiError) return { code: err.code, message: err.message };
  if (err instanceof NetworkError) return { message: err.message };
  if (err instanceof Error) return { message: err.message };
  return { message: 'Đã xảy ra lỗi không xác định.' };
}

/**
 * Drives one active Long-form TTS job end to end: submit -> poll -> terminal,
 * with an additional real cancel() path. Mirrors useTtsJobRunner's race/leak
 * safety pattern for the parts that carry over unchanged (see that file's
 * doc comment for the full rationale): a `generationRef` supersession
 * counter bumped on every new submit() and on unmount, checked before every
 * async continuation (submit response, each poll tick, cancel response)
 * touches state; a self-rescheduling setTimeout poll loop that stops on
 * COMPLETED/FAILED/CANCELLED or unmount; and bounded backoff on consecutive
 * poll failures.
 *
 * `runningRef` is intentionally narrower here than in useTtsJobRunner: it is
 * a purely SYNCHRONOUS lock that only spans "submit() was called" to "the
 * POST has actually been dispatched" - just enough to collapse a same-tick
 * double-click into one request (proven by a dedicated test). It is
 * released as soon as that POST round-trip settles (success or failure),
 * NOT held for the rest of the job's polling lifetime. Long-form's UI lets a
 * user submit a brand new job while an older one is still polling (the
 * generation counter above is what makes that safe - a late response from
 * the superseded job is simply discarded), and a lock held for the whole
 * lifetime would silently swallow that legitimate resubmission.
 *
 * Every response body read off `longFormJobService.get()`/`.cancel()` is
 * also guarded against being empty/undefined before touching `.status` on
 * it: `apiFetch()` returns `undefined` for a 2xx response with an empty
 * body rather than throwing (see its own doc comment), and while
 * `LongFormStatus` is documented as always present on these responses, a
 * malformed/empty one is treated as a normal, recoverable failure - it
 * flows into the exact same bounded-retry / resume-polling paths already
 * used for real network errors - rather than crashing on `undefined.status`.
 *
 * Other differences from useTtsJobRunner, following the real backend
 * contract:
 *  - no idempotency key (LongFormRequest has no such field, and
 *    extra="forbid" means sending one would be rejected outright);
 *  - a real cancel() that calls the DELETE endpoint instead of only
 *    detaching client-side tracking;
 *  - POLL_INTERVAL_MS = 1000, slower than Short TTS's 800ms, since a
 *    long-form job is expected to run far longer and progress_percent moves
 *    in coarser steps (whole chunks, not sub-second increments).
 */
export function useLongFormJobRunner(): UseLongFormJobRunnerResult {
  const [job, setJob] = useState<LongFormJob | null>(null);
  const [phase, setPhase] = useState<LongFormRunnerPhase>('idle');
  const [requestError, setRequestError] = useState<LongFormRunnerError | null>(null);

  const mountedRef = useRef(true);
  const runningRef = useRef(false);
  const generationRef = useRef(0);
  const pollTimeoutRef = useRef<number | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const consecutiveFailuresRef = useRef(0);
  const lastPayloadRef = useRef<LongFormFormPayload | null>(null);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      generationRef.current += 1; // supersede any in-flight submit/poll/cancel
      if (pollTimeoutRef.current !== null) {
        window.clearTimeout(pollTimeoutRef.current);
        pollTimeoutRef.current = null;
      }
      abortControllerRef.current?.abort();
    };
  }, []);

  const finishRun = useCallback((nextError: LongFormRunnerError | null) => {
    runningRef.current = false;
    if (!mountedRef.current) return;
    setPhase('idle');
    if (nextError) setRequestError(nextError);
  }, []);

  const schedulePoll = useCallback(
    (jobId: string, generation: number) => {
      const tick = async () => {
        if (!mountedRef.current || generationRef.current !== generation) return;

        const controller = new AbortController();
        abortControllerRef.current = controller;

        try {
          const latest = await longFormJobService.get(jobId, controller.signal);
          if (!mountedRef.current || generationRef.current !== generation) return;

          // A resolved (non-rejected) response is still not guaranteed to
          // carry a body: apiFetch() returns `undefined` for an
          // empty-bodied 2xx response (see its own doc comment) rather than
          // throwing. LongFormStatus is documented as always present on
          // this endpoint, but treating an empty/malformed response as a
          // thrown failure - rather than reading `.status` off it and
          // crashing - keeps this a real, recoverable runtime state instead
          // of an unhandled exception, and reuses the same bounded-retry
          // path as a network failure below.
          if (!latest) {
            throw new Error('Phản hồi không hợp lệ từ máy chủ (thiếu trạng thái tác vụ).');
          }

          consecutiveFailuresRef.current = 0;
          setJob(latest);

          if (isTerminalLongFormJobStatus(latest.status)) {
            finishRun(null); // terminal: stop polling, no further timer is scheduled
            return;
          }

          pollTimeoutRef.current = window.setTimeout(tick, POLL_INTERVAL_MS);
        } catch (err) {
          if (!mountedRef.current || generationRef.current !== generation) return;
          if (err instanceof DOMException && err.name === 'AbortError') return;

          consecutiveFailuresRef.current += 1;
          if (consecutiveFailuresRef.current >= MAX_CONSECUTIVE_POLL_FAILURES) {
            finishRun({
              message:
                'Mất kết nối tới máy chủ khi theo dõi tiến trình. Tác vụ có thể vẫn đang chạy trên backend.',
            });
            return; // bounded: give up instead of polling forever
          }

          const backoff = POLL_INTERVAL_MS * Math.min(consecutiveFailuresRef.current + 1, 5);
          pollTimeoutRef.current = window.setTimeout(tick, backoff);
        }
      };

      void tick();
    },
    [finishRun]
  );

  const submit = useCallback(
    async (payload: LongFormFormPayload) => {
      if (runningRef.current) return; // synchronous lock: collapses a same-tick double-submit only
      runningRef.current = true;

      lastPayloadRef.current = payload;

      const generation = ++generationRef.current;
      if (pollTimeoutRef.current !== null) {
        window.clearTimeout(pollTimeoutRef.current);
        pollTimeoutRef.current = null;
      }
      consecutiveFailuresRef.current = 0;

      setRequestError(null);
      setJob(null); // never show a stale/previous job's audio while a new one is in flight
      setPhase('submitting');

      const controller = new AbortController();
      abortControllerRef.current = controller;

      try {
        const created = await longFormJobService.submit(
          {
            text: payload.text,
            language: payload.language,
            profile_id: payload.profileId,
            format: payload.format,
          },
          controller.signal
        );
        // This attempt's POST round-trip is done - release the synchronous
        // lock now, unconditionally. It only ever needed to span "submit()
        // was called" to "the request has actually been dispatched", which
        // is what stops a double-click from firing two POSTs (proven by the
        // synchronous-double-submit test: a second, same-tick submit() call
        // is rejected before it ever reaches the request below, since JS
        // won't interleave with this function's own synchronous prefix).
        // Holding the lock any longer - for the rest of this job's polling
        // lifetime - would block a genuinely NEW submit() (the user edited
        // the form and generated again) from ever running, which is a real,
        // supported flow: job-B must be able to supersede a still-polling
        // job-A. That supersession is what the generation check right below
        // (and every check inside schedulePoll/cancel) is already
        // responsible for - this lock is not a second copy of that guard.
        runningRef.current = false;

        if (!mountedRef.current || generationRef.current !== generation) return; // superseded

        setJob(created);
        if (isTerminalLongFormJobStatus(created.status)) {
          finishRun(null);
          return;
        }
        setPhase('polling');
        schedulePoll(created.job_id, generation);
      } catch (err) {
        runningRef.current = false; // same reasoning as the success path above
        if (!mountedRef.current || generationRef.current !== generation) return;
        if (err instanceof DOMException && err.name === 'AbortError') return;
        finishRun(describeError(err));
      }
    },
    [finishRun, schedulePoll]
  );

  const cancel = useCallback(async () => {
    const current = job;
    if (!current || isTerminalLongFormJobStatus(current.status)) return;
    if (phase === 'cancelling') return;

    const generation = generationRef.current; // stay within the SAME generation as the active poll
    if (pollTimeoutRef.current !== null) {
      window.clearTimeout(pollTimeoutRef.current);
      pollTimeoutRef.current = null;
    }

    setPhase('cancelling');

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const updated = await longFormJobService.cancel(current.job_id, controller.signal);
      if (!mountedRef.current || generationRef.current !== generation) return; // superseded

      // Same defensive read as schedulePoll's tick(): a resolved response
      // can still be an empty body (apiFetch() returns `undefined` for
      // one rather than throwing). Route it through the catch block below
      // instead of dereferencing `.status` on it, so cancelling never
      // crashes and instead resumes polling on the last known-good job.
      if (!updated) {
        throw new Error('Phản hồi không hợp lệ từ máy chủ (thiếu trạng thái tác vụ) khi huỷ.');
      }

      setJob(updated);
      if (isTerminalLongFormJobStatus(updated.status)) {
        finishRun(null);
        return;
      }
      // Cancellation had not taken effect yet (still QUEUED/RUNNING) - resume
      // polling on the same job/generation until it actually goes terminal.
      setPhase('polling');
      schedulePoll(updated.job_id, generation);
    } catch (err) {
      if (!mountedRef.current || generationRef.current !== generation) return;
      if (err instanceof DOMException && err.name === 'AbortError') return;
      // Cancel itself failed (network/etc) - the job may still be running;
      // resume polling rather than leaving the UI stuck on "cancelling".
      setPhase('polling');
      schedulePoll(current.job_id, generation);
      setRequestError(describeError(err));
    }
  }, [job, phase, finishRun, schedulePoll]);

  const isBusy = phase === 'submitting' || phase === 'polling' || phase === 'cancelling';
  const canCancel = phase === 'polling' && job !== null && !isTerminalLongFormJobStatus(job.status);

  return {
    job,
    phase,
    requestError,
    isBusy,
    submit,
    cancel,
    canCancel,
    lastPayload: lastPayloadRef.current,
  };
}
