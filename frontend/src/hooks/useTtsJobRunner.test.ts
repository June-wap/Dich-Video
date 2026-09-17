import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError, NetworkError } from '../services/httpClient';
import type { TtsJob } from '../services/ttsJobService';

vi.mock('../services/ttsJobService', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../services/ttsJobService')>();
  return {
    ...actual,
    ttsJobService: {
      submit: vi.fn(),
      get: vi.fn(),
      list: vi.fn(),
      resolveAudioUrl: actual.ttsJobService.resolveAudioUrl,
      guessFormat: actual.ttsJobService.guessFormat,
    },
  };
});

import { ttsJobService } from '../services/ttsJobService';
import { useTtsJobRunner, type TtsFormPayload } from './useTtsJobRunner';

const submitMock = ttsJobService.submit as unknown as ReturnType<typeof vi.fn>;
const getMock = ttsJobService.get as unknown as ReturnType<typeof vi.fn>;

const payload: TtsFormPayload = {
  text: 'Xin chào thế giới',
  language: 'vi',
  voiceId: null,
  format: 'wav',
  speed: 1.0,
};

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (err: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

beforeEach(() => {
  vi.useFakeTimers();
  submitMock.mockReset();
  getMock.mockReset();
});

afterEach(() => {
  vi.useRealTimers();
});

describe('useTtsJobRunner', () => {
  it('submits -> QUEUED -> polls RUNNING -> COMPLETED, and stops polling at the terminal state', async () => {
    submitMock.mockResolvedValueOnce({ job_id: 'job-1', status: 'QUEUED' } satisfies TtsJob);

    // The hook fires its first poll GET immediately after the POST resolves
    // (no setTimeout gates it), so whether that GET has already resolved by
    // the time we assert is a microtask-ordering race, not something either
    // the test or the production code controls. To observe QUEUED
    // deterministically, hold the FIRST GET open with a manually-resolved
    // promise instead of a mock that resolves on its own - this proves the
    // job really is QUEUED immediately post-submit, before any poll response
    // has been applied, rather than asserting on a coin flip.
    const firstPoll = deferred<TtsJob>();
    getMock
      .mockImplementationOnce(() => firstPoll.promise) // 1st GET: held open deliberately
      .mockResolvedValueOnce({ job_id: 'job-1', status: 'COMPLETED', audio_url: '/api/audio/job-1.wav' } satisfies TtsJob); // 2nd GET, 800ms later

    const { result } = renderHook(() => useTtsJobRunner());

    await act(async () => {
      await result.current.submit(payload);
    });
    // POST established the job and polling started (the 1st GET was already
    // dispatched - registering a mock call happens synchronously, before its
    // promise is awaited) - but it has not resolved yet, so this is the real,
    // deterministic QUEUED state, not a race with the poll response.
    expect(result.current.phase).toBe('polling');
    expect(result.current.job?.job_id).toBe('job-1');
    expect(result.current.job?.status).toBe('QUEUED');
    expect(getMock).toHaveBeenCalledTimes(1);

    // Let the held-open 1st GET resolve to RUNNING (a non-terminal status -
    // proves non-terminal jobs keep polling and QUEUED/RUNNING are both
    // handled).
    await act(async () => {
      firstPoll.resolve({ job_id: 'job-1', status: 'RUNNING' });
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(result.current.job?.status).toBe('RUNNING');
    expect(result.current.phase).toBe('polling');
    expect(getMock).toHaveBeenCalledTimes(1); // next GET is scheduled 800ms out, not yet fired

    // Advance the real 800ms poll interval -> 2nd GET -> COMPLETED (terminal).
    await act(async () => {
      await vi.advanceTimersByTimeAsync(800);
    });
    expect(result.current.job?.status).toBe('COMPLETED');
    expect(result.current.job?.audio_url).toBe('/api/audio/job-1.wav');
    expect(result.current.phase).toBe('idle');
    expect(result.current.isBusy).toBe(false);
    expect(getMock).toHaveBeenCalledTimes(2);

    const callsAtCompletion = getMock.mock.calls.length;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });
    // No further/stale polling once terminal - a real backend job never
    // regresses, and polling forever after completion would be a leak.
    expect(getMock.mock.calls.length).toBe(callsAtCompletion);
  });

  it('surfaces a FAILED job with its error and allows retry', async () => {
    submitMock.mockResolvedValueOnce({ job_id: 'job-2', status: 'QUEUED' } satisfies TtsJob);
    getMock.mockResolvedValueOnce({
      job_id: 'job-2',
      status: 'FAILED',
      error: { code: 'GENERATION_FAILED', message: 'Quá trình tạo giọng nói thất bại.' },
    } satisfies TtsJob);

    const { result } = renderHook(() => useTtsJobRunner());
    await act(async () => {
      await result.current.submit(payload);
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(800);
    });

    expect(result.current.job?.status).toBe('FAILED');
    expect(result.current.job?.error?.code).toBe('GENERATION_FAILED');
    expect(result.current.phase).toBe('idle');
    expect(result.current.canRetry).toBe(true);
  });

  it('does not create a duplicate job on a synchronous double-submit', async () => {
    submitMock.mockResolvedValue({ job_id: 'job-3', status: 'COMPLETED', audio_url: '/api/audio/job-3.wav' } satisfies TtsJob);

    const { result } = renderHook(() => useTtsJobRunner());

    await act(async () => {
      // Two calls fired back-to-back, as a fast double-click would - the
      // second must be ignored by the hook's synchronous lock.
      void result.current.submit(payload);
      await result.current.submit(payload);
    });

    expect(submitMock).toHaveBeenCalledTimes(1);
  });

  it('reuses the same idempotency key for an unedited resubmission, and a different key when the payload changes', async () => {
    submitMock.mockResolvedValue({ job_id: 'job-4', status: 'COMPLETED' } satisfies TtsJob);
    const { result } = renderHook(() => useTtsJobRunner());

    await act(async () => {
      await result.current.submit(payload);
    });
    const firstKey = submitMock.mock.calls[0][0].idempotency_key;

    await act(async () => {
      await result.current.submit(payload); // identical payload again
    });
    const secondKey = submitMock.mock.calls[1][0].idempotency_key;
    expect(secondKey).toBe(firstKey);

    await act(async () => {
      await result.current.submit({ ...payload, text: 'Một văn bản khác hẳn' });
    });
    const thirdKey = submitMock.mock.calls[2][0].idempotency_key;
    expect(thirdKey).not.toBe(firstKey);
  });

  it('retry after a FAILED job uses a NEW idempotency key, not the failed attempt\'s key', async () => {
    submitMock.mockResolvedValueOnce({ job_id: 'job-5', status: 'QUEUED' } satisfies TtsJob);
    getMock.mockResolvedValueOnce({
      job_id: 'job-5',
      status: 'FAILED',
      error: { code: 'GENERATION_FAILED', message: 'Thất bại' },
    } satisfies TtsJob);

    const { result } = renderHook(() => useTtsJobRunner());
    await act(async () => {
      await result.current.submit(payload);
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(800);
    });
    const failedKey = submitMock.mock.calls[0][0].idempotency_key;
    expect(result.current.job?.status).toBe('FAILED');

    submitMock.mockResolvedValueOnce({ job_id: 'job-5-retry', status: 'COMPLETED' } satisfies TtsJob);
    await act(async () => {
      await result.current.retry();
    });

    const retryKey = submitMock.mock.calls[1][0].idempotency_key;
    expect(retryKey).not.toBe(failedKey);
    expect(result.current.job?.job_id).toBe('job-5-retry');
  });

  it('surfaces HTTP 409 IDEMPOTENCY_KEY_CONFLICT as a clear, retryable request error', async () => {
    submitMock.mockRejectedValueOnce(new ApiError('IDEMPOTENCY_KEY_CONFLICT', 'Khóa idempotency đã được dùng.', 409));

    const { result } = renderHook(() => useTtsJobRunner());
    await act(async () => {
      await result.current.submit(payload);
    });

    expect(result.current.job).toBeNull();
    expect(result.current.requestError?.code).toBe('IDEMPOTENCY_KEY_CONFLICT');
    expect(result.current.phase).toBe('idle');
    expect(result.current.canRetry).toBe(true);
  });

  it('surfaces a network failure on submit as a recoverable request error', async () => {
    submitMock.mockRejectedValueOnce(new NetworkError('Không thể kết nối tới máy chủ.'));

    const { result } = renderHook(() => useTtsJobRunner());
    await act(async () => {
      await result.current.submit(payload);
    });

    expect(result.current.requestError?.message).toMatch(/kết nối/i);
    expect(result.current.canRetry).toBe(true);
  });

  it('stops polling once the component unmounts (no leaked timers/requests)', async () => {
    submitMock.mockResolvedValueOnce({ job_id: 'job-6', status: 'QUEUED' } satisfies TtsJob);
    getMock.mockResolvedValue({ job_id: 'job-6', status: 'RUNNING' } satisfies TtsJob);

    const { result, unmount } = renderHook(() => useTtsJobRunner());
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

  it('never lets a stale (superseded) response overwrite a newer job\'s state', async () => {
    const jobADeferred = deferred<TtsJob>();
    submitMock.mockResolvedValueOnce({ job_id: 'job-A', status: 'QUEUED' } satisfies TtsJob);
    getMock.mockImplementationOnce(() => jobADeferred.promise); // job A's first poll tick hangs

    const { result } = renderHook(() => useTtsJobRunner());
    await act(async () => {
      await result.current.submit(payload);
    });
    expect(result.current.job?.job_id).toBe('job-A');

    // Abandon job A's tracking, then immediately submit a different job B
    // that resolves as already COMPLETED (idempotent replay style response).
    act(() => {
      result.current.cancelTracking();
    });
    submitMock.mockResolvedValueOnce({
      job_id: 'job-B',
      status: 'COMPLETED',
      audio_url: '/api/audio/job-B.wav',
    } satisfies TtsJob);
    await act(async () => {
      await result.current.submit({ ...payload, text: 'Văn bản của job B' });
    });
    expect(result.current.job?.job_id).toBe('job-B');

    // Job A's long-pending poll finally resolves - it must be discarded, not
    // overwrite job B's state, because it belongs to a superseded generation.
    await act(async () => {
      jobADeferred.resolve({ job_id: 'job-A', status: 'RUNNING' });
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(result.current.job?.job_id).toBe('job-B');
    expect(result.current.job?.status).toBe('COMPLETED');
  });
});
