import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { NetworkError } from '../services/httpClient';
import type { LongFormJob } from '../services/longFormJobService';

vi.mock('../services/longFormJobService', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../services/longFormJobService')>();
  return {
    ...actual,
    longFormJobService: {
      submit: vi.fn(),
      get: vi.fn(),
      cancel: vi.fn(),
      resolveAudioUrl: actual.longFormJobService.resolveAudioUrl,
      guessFormat: actual.longFormJobService.guessFormat,
    },
  };
});

import { longFormJobService } from '../services/longFormJobService';
import { useLongFormJobRunner, type LongFormFormPayload } from './useLongFormJobRunner';

const submitMock = longFormJobService.submit as unknown as ReturnType<typeof vi.fn>;
const getMock = longFormJobService.get as unknown as ReturnType<typeof vi.fn>;
const cancelMock = longFormJobService.cancel as unknown as ReturnType<typeof vi.fn>;

const payload: LongFormFormPayload = {
  text: 'Một đoạn văn bản dài để kiểm thử.',
  language: 'vi',
  profileId: 'profile-1',
  format: 'wav',
};

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((res) => {
    resolve = res;
  });
  return { promise, resolve };
}

beforeEach(() => {
  vi.useFakeTimers();
  submitMock.mockReset();
  getMock.mockReset();
  cancelMock.mockReset();
});

afterEach(() => {
  vi.useRealTimers();
});

describe('useLongFormJobRunner', () => {
  it('submits -> QUEUED -> polls RUNNING (real progress_percent) -> COMPLETED, and stops polling at the terminal state', async () => {
    submitMock.mockResolvedValueOnce({ job_id: 'job-1', status: 'QUEUED', progress_percent: 0 } satisfies LongFormJob);

    const firstPoll = deferred<LongFormJob>();
    getMock
      .mockImplementationOnce(() => firstPoll.promise)
      .mockResolvedValueOnce({
        job_id: 'job-1',
        status: 'COMPLETED',
        progress_percent: 100,
        audio_url: '/api/audio/job-1.wav',
      } satisfies LongFormJob);

    const { result } = renderHook(() => useLongFormJobRunner());

    await act(async () => {
      await result.current.submit(payload);
    });
    expect(result.current.phase).toBe('polling');
    expect(result.current.job?.status).toBe('QUEUED');
    expect(getMock).toHaveBeenCalledTimes(1);

    await act(async () => {
      firstPoll.resolve({ job_id: 'job-1', status: 'RUNNING', progress_percent: 37 });
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(result.current.job?.status).toBe('RUNNING');
    expect(result.current.job?.progress_percent).toBe(37); // a real backend-computed number, never simulated
    expect(getMock).toHaveBeenCalledTimes(1); // next GET is scheduled 1000ms out

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });
    expect(result.current.job?.status).toBe('COMPLETED');
    expect(result.current.job?.audio_url).toBe('/api/audio/job-1.wav');
    expect(result.current.phase).toBe('idle');
    expect(result.current.isBusy).toBe(false);

    const callsAtCompletion = getMock.mock.calls.length;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });
    expect(getMock.mock.calls.length).toBe(callsAtCompletion); // no stale polling after terminal
  });

  it('surfaces a FAILED job with its error', async () => {
    submitMock.mockResolvedValueOnce({ job_id: 'job-2', status: 'QUEUED', progress_percent: 0 } satisfies LongFormJob);
    getMock.mockResolvedValueOnce({
      job_id: 'job-2',
      status: 'FAILED',
      progress_percent: 60,
      error: { code: 'GENERATION_FAILED', message: 'Quá trình tạo audio thất bại.' },
    } satisfies LongFormJob);

    const { result } = renderHook(() => useLongFormJobRunner());
    await act(async () => {
      await result.current.submit(payload);
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });

    expect(result.current.job?.status).toBe('FAILED');
    expect(result.current.job?.error?.code).toBe('GENERATION_FAILED');
    expect(result.current.phase).toBe('idle');
  });

  it('cancel(): a RUNNING job whose cancel response is still RUNNING keeps polling (checked only between chunks) until it actually goes CANCELLED', async () => {
    submitMock.mockResolvedValueOnce({ job_id: 'job-3', status: 'QUEUED', progress_percent: 0 } satisfies LongFormJob);
    getMock.mockResolvedValueOnce({ job_id: 'job-3', status: 'RUNNING', progress_percent: 50 } satisfies LongFormJob);

    const { result } = renderHook(() => useLongFormJobRunner());
    await act(async () => {
      await result.current.submit(payload);
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });
    expect(result.current.job?.status).toBe('RUNNING');
    expect(result.current.canCancel).toBe(true);

    // DELETE responds but cancellation had not taken effect yet. cancel()'s
    // success handler treats a non-terminal response as "resume polling",
    // which calls schedulePoll() - and schedulePoll fires its FIRST tick
    // synchronously (`void tick()`, no setTimeout gate), exactly like the
    // very first poll after submit() above (see that test's own comment on
    // this same race). So the GET that actually observes CANCELLED is the
    // one fired by *that* immediate resumed tick, not a later poll gated by
    // POLL_INTERVAL_MS - arm it before calling cancel(), not after a
    // subsequent timer advance.
    cancelMock.mockResolvedValueOnce({ job_id: 'job-3', status: 'RUNNING', progress_percent: 52 } satisfies LongFormJob);
    getMock.mockResolvedValueOnce({ job_id: 'job-3', status: 'CANCELLED', progress_percent: 52 } satisfies LongFormJob);
    await act(async () => {
      await result.current.cancel();
    });
    // cancel() always passes a real AbortSignal (from its own AbortController)
    // as the second argument - it's never `undefined` in production, so
    // assert its actual shape instead of a literal `undefined` match.
    expect(cancelMock).toHaveBeenCalledTimes(1);
    const [calledJobId, calledSignal] = cancelMock.mock.calls[0];
    expect(calledJobId).toBe('job-3');
    if (!calledSignal) {
      throw new Error('longFormJobService.cancel was called without a signal argument');
    }
    expect(calledSignal).toBeInstanceOf(AbortSignal);
    expect(calledSignal.aborted).toBe(false); // not aborted at the moment cancel() invoked it

    // By the time cancel() settles, its immediate resumed poll has already
    // observed CANCELLED - this is a stronger check than asserting the
    // intermediate RUNNING/'polling' state, since the job could only reach
    // CANCELLED at all if the RUNNING cancel response was correctly treated
    // as non-terminal and polling actually resumed and continued.
    expect(result.current.job?.status).toBe('CANCELLED');
    expect(result.current.phase).toBe('idle');
    expect(result.current.canCancel).toBe(false);
  });

  it('does not crash when a poll response is malformed (undefined) - treats it as a retryable failure like a network error', async () => {
    submitMock.mockResolvedValueOnce({ job_id: 'job-7', status: 'QUEUED', progress_percent: 0 } satisfies LongFormJob);
    // apiFetch() returns `undefined` for a resolved-but-empty-bodied
    // response rather than throwing (see httpClient.ts) - simulate that
    // exact shape, every poll, to drive the bounded-retry path to give up.
    getMock.mockResolvedValue(undefined as unknown as LongFormJob);

    const { result } = renderHook(() => useLongFormJobRunner());
    await act(async () => {
      await result.current.submit(payload);
    });
    expect(result.current.job?.status).toBe('QUEUED');

    // MAX_CONSECUTIVE_POLL_FAILURES is 5 - advance through all of them.
    for (let i = 0; i < 5; i += 1) {
      await act(async () => {
        await vi.advanceTimersByTimeAsync(5000);
      });
    }

    // Must never have thrown/crashed reading `.status` off `undefined`, and
    // must surface as a normal recoverable error, exactly like a run of
    // network failures - not silently, and not by weakening this assertion.
    expect(result.current.phase).toBe('idle');
    expect(result.current.requestError).not.toBeNull();
    // The job set from the QUEUED submit response must still be intact -
    // an invalid poll response must never overwrite it with `undefined`.
    expect(result.current.job?.job_id).toBe('job-7');
    expect(result.current.job?.status).toBe('QUEUED');
  });

  it('does not crash when cancel() gets a malformed (undefined) response - resumes polling on the last known-good job and surfaces an error', async () => {
    submitMock.mockResolvedValueOnce({ job_id: 'job-8', status: 'QUEUED', progress_percent: 0 } satisfies LongFormJob);
    getMock.mockResolvedValueOnce({ job_id: 'job-8', status: 'RUNNING', progress_percent: 30 } satisfies LongFormJob);

    const { result } = renderHook(() => useLongFormJobRunner());
    await act(async () => {
      await result.current.submit(payload);
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });
    expect(result.current.job?.status).toBe('RUNNING');

    // apiFetch() returns `undefined` for an empty-bodied cancel response.
    cancelMock.mockResolvedValueOnce(undefined as unknown as LongFormJob);
    // cancel()'s catch resumes polling immediately (schedulePoll fires a
    // tick synchronously) - arm the next GET so that resumed tick succeeds
    // cleanly and the poll cadence stays on the normal 1000ms interval
    // rather than a failure backoff, keeping the rest of this test's timing
    // simple and independent of the retry/backoff math exercised above.
    getMock.mockResolvedValueOnce({ job_id: 'job-8', status: 'RUNNING', progress_percent: 31 } satisfies LongFormJob);
    await act(async () => {
      await result.current.cancel();
    });

    // Must never have thrown/crashed reading `.status` off `undefined`.
    expect(result.current.job?.job_id).toBe('job-8');
    expect(result.current.job?.status).toBe('RUNNING'); // last known-good state, not clobbered
    expect(result.current.phase).toBe('polling'); // resumed, not stuck on "cancelling"
    expect(result.current.requestError).not.toBeNull();

    // And polling genuinely continues on the same job afterward.
    getMock.mockResolvedValueOnce({ job_id: 'job-8', status: 'CANCELLED', progress_percent: 30 } satisfies LongFormJob);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });
    expect(result.current.job?.status).toBe('CANCELLED');
    expect(result.current.phase).toBe('idle');
  });

  it('cancel() is a no-op once the job is already terminal', async () => {
    submitMock.mockResolvedValueOnce({
      job_id: 'job-4',
      status: 'COMPLETED',
      progress_percent: 100,
      audio_url: '/api/audio/job-4.wav',
    } satisfies LongFormJob);

    const { result } = renderHook(() => useLongFormJobRunner());
    await act(async () => {
      await result.current.submit(payload);
    });
    expect(result.current.job?.status).toBe('COMPLETED');

    await act(async () => {
      await result.current.cancel();
    });
    expect(cancelMock).not.toHaveBeenCalled();
  });

  it('does not create a duplicate job on a synchronous double-submit', async () => {
    submitMock.mockResolvedValue({
      job_id: 'job-5',
      status: 'COMPLETED',
      progress_percent: 100,
      audio_url: '/api/audio/job-5.wav',
    } satisfies LongFormJob);

    const { result } = renderHook(() => useLongFormJobRunner());
    await act(async () => {
      void result.current.submit(payload);
      await result.current.submit(payload);
    });

    expect(submitMock).toHaveBeenCalledTimes(1);
  });

  it('surfaces a network failure on submit as a recoverable request error', async () => {
    submitMock.mockRejectedValueOnce(new NetworkError('Không thể kết nối tới máy chủ.'));

    const { result } = renderHook(() => useLongFormJobRunner());
    await act(async () => {
      await result.current.submit(payload);
    });

    expect(result.current.requestError?.message).toMatch(/kết nối/i);
    expect(result.current.phase).toBe('idle');
  });

  it('stops polling once the component unmounts (no leaked timers/requests)', async () => {
    submitMock.mockResolvedValueOnce({ job_id: 'job-6', status: 'QUEUED', progress_percent: 0 } satisfies LongFormJob);
    getMock.mockResolvedValue({ job_id: 'job-6', status: 'RUNNING', progress_percent: 10 } satisfies LongFormJob);

    const { result, unmount } = renderHook(() => useLongFormJobRunner());
    await act(async () => {
      await result.current.submit(payload);
    });

    const callsBeforeUnmount = getMock.mock.calls.length;
    unmount();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });

    expect(getMock.mock.calls.length).toBe(callsBeforeUnmount);
  });

  it("never lets a stale (superseded) poll response overwrite a newer job's state", async () => {
    const jobADeferred = deferred<LongFormJob>();
    submitMock.mockResolvedValueOnce({ job_id: 'job-A', status: 'QUEUED', progress_percent: 0 } satisfies LongFormJob);
    getMock.mockImplementationOnce(() => jobADeferred.promise);

    const { result } = renderHook(() => useLongFormJobRunner());
    await act(async () => {
      await result.current.submit(payload);
    });
    expect(result.current.job?.job_id).toBe('job-A');

    // A fresh submit() (e.g. the user edited the form and generated again)
    // supersedes job A's in-flight poll.
    submitMock.mockResolvedValueOnce({
      job_id: 'job-B',
      status: 'COMPLETED',
      progress_percent: 100,
      audio_url: '/api/audio/job-B.wav',
    } satisfies LongFormJob);
    await act(async () => {
      await result.current.submit({ ...payload, text: 'Văn bản khác của job B' });
    });
    expect(result.current.job?.job_id).toBe('job-B');

    // Job A's long-pending poll finally resolves - must be discarded.
    await act(async () => {
      jobADeferred.resolve({ job_id: 'job-A', status: 'RUNNING', progress_percent: 20 });
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(result.current.job?.job_id).toBe('job-B');
    expect(result.current.job?.status).toBe('COMPLETED');
  });
});
