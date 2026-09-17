import { useCallback, useEffect, useRef, useState } from 'react';
import {
  ttsJobService,
  isTerminalTtsJobStatus,
  type TtsJob,
  type SubmitTtsJobPayload,
  type TtsAudioFormat,
} from '../services/ttsJobService';
import { ApiError, NetworkError } from '../services/httpClient';

const POLL_INTERVAL_MS = 800;
const MAX_CONSECUTIVE_POLL_FAILURES = 5;

export interface TtsFormPayload {
  text: string;
  language: string;
  voiceId: string | null;
  format: TtsAudioFormat;
  speed: number;
}

export type TtsRunnerPhase = 'idle' | 'submitting' | 'polling';

export interface TtsRunnerError {
  code?: string;
  message: string;
}

export interface UseTtsJobRunnerResult {
  job: TtsJob | null;
  phase: TtsRunnerPhase;
  requestError: TtsRunnerError | null;
  /** True while a submit is in flight or an active job is being polled -
   * drives the Generate button's disabled/loading state. */
  isBusy: boolean;
  submit: (payload: TtsFormPayload) => Promise<void>;
  /** Re-attempts the last payload as a NEW operation (fresh idempotency
   * key), so retrying a FAILED job never just redisplays the same failure -
   * see the idempotency-key derivation notes below. */
  retry: () => Promise<void>;
  canRetry: boolean;
  /**
   * Stops watching the active job (clears polling and local state) WITHOUT
   * cancelling it server-side - the Short TTS Job API has no cancel
   * endpoint, so generation keeps running on the backend regardless. Purely
   * a "stop showing me this" affordance for the UI.
   */
  cancelTracking: () => void;
  /** The payload that produced the current `job` (or was last attempted).
   * Exposed so callers can enrich a job with form-side context the backend
   * does not echo back (e.g. a local, non-persisted text/voice preview for
   * a history row) without re-deriving it from possibly-since-edited form
   * state. */
  lastPayload: TtsFormPayload | null;
}

/**
 * djb2 - a small, dependency-free, deterministic string hash. It does not
 * need to be cryptographic, only a stable function of (session salt,
 * payload, attempt) so that:
 *   - an unedited resubmission of the same payload WITHIN THE SAME MOUNT
 *     (browser tab, not reloaded) always derives the SAME idempotency key
 *     (server dedupes it -> reuses the existing job), and
 *   - any change to the payload, OR an explicit Retry after FAILED, always
 *     derives a DIFFERENT key (server treats it as a new job).
 *
 * The server persists (idempotency_key -> fingerprint) FOREVER across all
 * past jobs (backend/persistence.py find_job_by_idempotency_key scans the
 * whole history, no expiry, no session scoping - see
 * backend/services/tts_service.py IDEMPOTENCY_KEY_CONFLICT). A key derived
 * from content alone would therefore collide with an unrelated job from a
 * PAST session the moment the same (or similarly-hashing) text/language is
 * submitted again after reloading the page - this was reported as
 * "IDEMPOTENCY_KEY_CONFLICT on every reopen" and is why the session salt
 * below exists: it is randomized once per mount and mixed into every key,
 * so keys from different page loads never collide server-side, while
 * same-mount dedup (the actual intended use of this key) is untouched.
 */
function stableHash(input: string): string {
  let hash = 5381;
  for (let i = 0; i < input.length; i += 1) {
    hash = (hash * 33) ^ input.charCodeAt(i);
  }
  return (hash >>> 0).toString(36);
}

function normalizePayloadForKey(payload: TtsFormPayload): string {
  return JSON.stringify({
    text: payload.text.trim(),
    language: payload.language,
    voiceId: payload.voiceId || null,
    format: payload.format,
    speed: payload.speed,
  });
}

function describeError(err: unknown): TtsRunnerError {
  if (err instanceof ApiError) return { code: err.code, message: err.message };
  if (err instanceof NetworkError) return { message: err.message };
  if (err instanceof Error) return { message: err.message };
  return { message: 'Đã xảy ra lỗi không xác định.' };
}

/**
 * Drives one active Short TTS job end to end: submit -> poll -> terminal.
 *
 * Race/leak safety:
 *  - `runningRef` is a synchronous lock (not React state, which batches) so
 *    two submit() calls fired back-to-back in the same tick - e.g. a fast
 *    double-click before the button's disabled prop re-renders - can only
 *    ever start one attempt. The idempotency key is a second, server-side
 *    backstop against the same duplication (e.g. a retried network request).
 *  - `generationRef` is bumped on every new submit() and on unmount; every
 *    async continuation (submit response, each poll tick) checks it before
 *    touching state, so a response belonging to a superseded job can never
 *    overwrite state for a newer one, and unmount silently stops everything.
 *  - Polling is a self-rescheduling setTimeout chain (never setInterval), so
 *    there is exactly one pending timer per job and it only re-arms itself
 *    while the job is non-terminal; it stops immediately on COMPLETED/FAILED
 *    and is cleared on unmount/supersession.
 *  - A run of consecutive network failures while polling is bounded
 *    (MAX_CONSECUTIVE_POLL_FAILURES) with linear backoff, then gives up with
 *    a recoverable error instead of polling forever.
 */
export function useTtsJobRunner(): UseTtsJobRunnerResult {
  const [job, setJob] = useState<TtsJob | null>(null);
  const [phase, setPhase] = useState<TtsRunnerPhase>('idle');
  const [requestError, setRequestError] = useState<TtsRunnerError | null>(null);

  const mountedRef = useRef(true);
  const runningRef = useRef(false);
  const generationRef = useRef(0);
  const pollTimeoutRef = useRef<number | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const consecutiveFailuresRef = useRef(0);

  const lastPayloadKeyRef = useRef<string | null>(null);
  const attemptNonceRef = useRef(0);
  const lastPayloadRef = useRef<TtsFormPayload | null>(null);

  // Randomized once per mount (see stableHash's docstring above) so the
  // idempotency key can never collide with a job from a previous page load.
  // Written during render, not an effect - this is React's documented
  // pattern for one-time lazy ref initialization, and it is idempotent
  // (the if-guard means a second render in the same mount, e.g. StrictMode,
  // does not overwrite an already-assigned salt).
  const sessionSaltRef = useRef<string | null>(null);
  if (sessionSaltRef.current === null) {
    sessionSaltRef.current =
      typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
        ? crypto.randomUUID()
        : `${Date.now()}-${Math.random()}`;
  }

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      generationRef.current += 1; // supersede any in-flight submit/poll
      if (pollTimeoutRef.current !== null) {
        window.clearTimeout(pollTimeoutRef.current);
        pollTimeoutRef.current = null;
      }
      abortControllerRef.current?.abort();
    };
  }, []);

  const computeIdempotencyKey = useCallback((payload: TtsFormPayload, forceNewAttempt: boolean): string => {
    const normalized = normalizePayloadForKey(payload);
    if (normalized !== lastPayloadKeyRef.current) {
      attemptNonceRef.current = 0;
      lastPayloadKeyRef.current = normalized;
    } else if (forceNewAttempt) {
      attemptNonceRef.current += 1;
    }
    return stableHash(`${sessionSaltRef.current}:${normalized}:${attemptNonceRef.current}`);
  }, []);

  const finishRun = useCallback((nextError: TtsRunnerError | null) => {
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
          const latest = await ttsJobService.get(jobId, controller.signal);
          if (!mountedRef.current || generationRef.current !== generation) return;

          consecutiveFailuresRef.current = 0;
          setJob(latest);

          if (isTerminalTtsJobStatus(latest.status)) {
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
                'Mất kết nối tới máy chủ khi theo dõi tiến trình. Tác vụ có thể vẫn đang chạy trên backend - hãy tải lại lịch sử để kiểm tra.',
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

  const runSubmit = useCallback(
    async (payload: TtsFormPayload, forceNewAttempt: boolean) => {
      if (runningRef.current) return; // synchronous lock: one attempt/poll loop at a time
      runningRef.current = true;

      lastPayloadRef.current = payload;
      const idempotencyKey = computeIdempotencyKey(payload, forceNewAttempt);

      const generation = ++generationRef.current;
      if (pollTimeoutRef.current !== null) {
        window.clearTimeout(pollTimeoutRef.current);
        pollTimeoutRef.current = null;
      }
      consecutiveFailuresRef.current = 0;

      setRequestError(null);
      setJob(null); // never show stale audio from a previous job while a new one is in flight
      setPhase('submitting');

      const controller = new AbortController();
      abortControllerRef.current = controller;

      const body: SubmitTtsJobPayload = {
        text: payload.text,
        language: payload.language,
        voice_id: payload.voiceId || null,
        speed: payload.speed,
        format: payload.format,
        idempotency_key: idempotencyKey,
      };

      try {
        const created = await ttsJobService.submit(body, controller.signal);
        if (!mountedRef.current || generationRef.current !== generation) return; // superseded

        setJob(created);
        if (isTerminalTtsJobStatus(created.status)) {
          // An idempotent replay of an already-finished job returns it
          // immediately - nothing to poll.
          finishRun(null);
          return;
        }
        setPhase('polling');
        schedulePoll(created.job_id, generation);
      } catch (err) {
        if (!mountedRef.current || generationRef.current !== generation) {
          runningRef.current = false; // superseded before we could react; still release the lock
          return;
        }
        if (err instanceof DOMException && err.name === 'AbortError') {
          runningRef.current = false;
          return;
        }
        finishRun(describeError(err));
      }
    },
    [computeIdempotencyKey, finishRun, schedulePoll]
  );

  const submit = useCallback((payload: TtsFormPayload) => runSubmit(payload, false), [runSubmit]);

  const retry = useCallback(() => {
    const payload = lastPayloadRef.current;
    if (!payload) return Promise.resolve();
    return runSubmit(payload, true);
  }, [runSubmit]);

  const cancelTracking = useCallback(() => {
    generationRef.current += 1; // supersede any in-flight submit/poll
    if (pollTimeoutRef.current !== null) {
      window.clearTimeout(pollTimeoutRef.current);
      pollTimeoutRef.current = null;
    }
    abortControllerRef.current?.abort();
    runningRef.current = false;
    setPhase('idle');
    setJob(null);
    setRequestError(null);
  }, []);

  const isBusy = phase === 'submitting' || phase === 'polling';
  const canRetry = phase === 'idle' && (requestError !== null || job?.status === 'FAILED');

  return {
    job,
    phase,
    requestError,
    isBusy,
    submit,
    retry,
    canRetry,
    cancelTracking,
    lastPayload: lastPayloadRef.current,
  };
}
