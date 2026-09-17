import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError, NetworkError } from '../services/httpClient';
import type { TtsJob } from '../services/ttsJobService';

// Only submit/get/list touch the network - resolveAudioUrl/guessFormat stay
// real so the rendered <audio src> and format badges reflect the actual
// origin-qualifying logic under test elsewhere (ttsJobService.test.ts).
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

// TTSPage reads Settings > Audio > Output Format (for its one-time format
// pre-fill) and Settings > General's notification toggles via useAppSettings()
// (see AppSettingsContext.tsx) - added after this file's other tests were
// written, so TTSPage now throws "useAppSettings must be used within
// AppSettingsProvider" unless that context is available. Mocking the hook
// directly here (rather than wrapping every render(<TTSPage />) call in the
// real <AppSettingsProvider>) avoids a real GET /api/settings/app network
// call per test and keeps every existing test's assertions valid: mock
// output_format is 'wav' (matches the WAV-default assertions already in this
// file) and both notification toggles are off (no Notification side effects
// to account for in tests that don't care about them).
vi.mock('../context/AppSettingsContext', () => ({
  useAppSettings: () => ({
    settings: {
      app_lang: 'vi',
      app_theme: 'light',
      notify_completion: false,
      notify_errors: false,
      output_format: 'wav',
      pause_policy_ms: 400,
      silence_trim: false,
      output_dir: null,
      device: 'gpu',
      quality_preset: 'balanced',
      retry_count: 1,
      num_steps: 16,
      debug_logs: false,
      actual_db_path: '',
      actual_output_dir: '',
      output_dir_bytes: 0,
    },
    loading: false,
    error: null,
    reload: vi.fn(),
    save: vi.fn(),
  }),
}));

import { ttsJobService } from '../services/ttsJobService';
import { API_BASE_URL } from '../services/httpClient';
import { TTSPage } from './TTSPage';

const API_ORIGIN = new URL(API_BASE_URL).origin;

const submitMock = ttsJobService.submit as unknown as ReturnType<typeof vi.fn>;
const getMock = ttsJobService.get as unknown as ReturnType<typeof vi.fn>;
const listMock = ttsJobService.list as unknown as ReturnType<typeof vi.fn>;

beforeEach(() => {
  submitMock.mockReset();
  getMock.mockReset();
  listMock.mockReset();
  listMock.mockResolvedValue([]); // empty history by default unless a test overrides it
});

afterEach(() => {
  vi.restoreAllMocks();
});

/** Waits out the page's initial GET /api/tts/jobs history load. */
async function waitForHistoryToSettle() {
  await waitFor(() => expect(screen.queryByText('Đang tải lịch sử...')).not.toBeInTheDocument());
}

describe('TTSPage', () => {
  it('renders the form with a WAV default and no fake progress percentage anywhere', async () => {
    render(<TTSPage />);
    await waitForHistoryToSettle();

    expect(screen.getByRole('textbox', { name: /văn bản cần đọc/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/định dạng xuất/i)).toHaveValue('wav');
    expect(screen.getByRole('button', { name: /tạo giọng nói/i })).toBeEnabled();
  });

  it('submits, reaches COMPLETED, and renders a real playable + downloadable WAV result (no reconstructed URL)', async () => {
    submitMock.mockResolvedValueOnce({
      job_id: 'job-wav-1',
      status: 'COMPLETED',
      audio_url: '/api/audio/job-wav-1.wav',
    } satisfies TtsJob);

    const user = userEvent.setup();
    render(<TTSPage />);
    await waitForHistoryToSettle();

    await user.click(screen.getByRole('button', { name: /tạo giọng nói/i }));

    await screen.findByText('Tạo âm thanh thành công');
    const audioEl = document.querySelector('audio');
    expect(audioEl).toBeTruthy();
    // The audio_url is only origin-qualified, never rebuilt from parts.
    expect(audioEl).toHaveAttribute('src', `${API_ORIGIN}/api/audio/job-wav-1.wav`);
    expect(screen.getByText('WAV')).toBeInTheDocument();

    const downloadLink = screen.getByRole('link', { name: /tải xuống wav/i });
    expect(downloadLink).toHaveAttribute('href', `${API_ORIGIN}/api/audio/job-wav-1.wav`);
    expect(downloadLink).toHaveAttribute('download');
  });

  it('submits an MP3 job (format selector honored) and renders the MP3 result', async () => {
    submitMock.mockResolvedValueOnce({
      job_id: 'job-mp3-1',
      status: 'COMPLETED',
      audio_url: '/api/audio/job-mp3-1.mp3',
    } satisfies TtsJob);

    const user = userEvent.setup();
    render(<TTSPage />);
    await waitForHistoryToSettle();

    await user.selectOptions(screen.getByLabelText(/định dạng xuất/i), 'mp3');
    await user.click(screen.getByRole('button', { name: /tạo giọng nói/i }));

    await screen.findByText('Tạo âm thanh thành công');
    expect(submitMock).toHaveBeenCalledWith(expect.objectContaining({ format: 'mp3' }), expect.anything());
    expect(screen.getByText('MP3')).toBeInTheDocument();
    const audioEl = document.querySelector('audio');
    expect(audioEl).toHaveAttribute('src', `${API_ORIGIN}/api/audio/job-mp3-1.mp3`);
  });

  it('shows a validation error near the form/action and never calls submit for empty text', async () => {
    const user = userEvent.setup();
    render(<TTSPage />);
    await waitForHistoryToSettle();

    await user.clear(screen.getByRole('textbox', { name: /văn bản cần đọc/i }));
    await user.click(screen.getByRole('button', { name: /tạo giọng nói/i }));

    expect(await screen.findByText('Vui lòng nhập nội dung văn bản trước khi tạo giọng nói.')).toBeInTheDocument();
    expect(submitMock).not.toHaveBeenCalled();
  });

  it('surfaces a FAILED job with a meaningful error and a working Retry that starts a new attempt', async () => {
    submitMock.mockResolvedValueOnce({
      job_id: 'job-fail-1',
      status: 'FAILED',
      error: { code: 'GENERATION_FAILED', message: 'Không thể tổng hợp giọng nói do lỗi mô hình.' },
    } satisfies TtsJob);

    const user = userEvent.setup();
    render(<TTSPage />);
    await waitForHistoryToSettle();

    await user.click(screen.getByRole('button', { name: /tạo giọng nói/i }));

    expect((await screen.findAllByText('Không thể tổng hợp giọng nói do lỗi mô hình.')).length).toBeGreaterThan(0);

    submitMock.mockResolvedValueOnce({
      job_id: 'job-fail-1-retry',
      status: 'COMPLETED',
      audio_url: '/api/audio/job-fail-1-retry.wav',
    } satisfies TtsJob);

    await user.click(screen.getByRole('button', { name: /thử lại/i }));

    await screen.findByText('Tạo âm thanh thành công');
    expect(submitMock).toHaveBeenCalledTimes(2);
  });

  it('surfaces an HTTP 409 idempotency conflict as a clear inline error, not a crash', async () => {
    submitMock.mockRejectedValueOnce(new ApiError('IDEMPOTENCY_KEY_CONFLICT', 'Yêu cầu đã tồn tại với nội dung khác.', 409));

    const user = userEvent.setup();
    render(<TTSPage />);
    await waitForHistoryToSettle();

    await user.click(screen.getByRole('button', { name: /tạo giọng nói/i }));

    expect((await screen.findAllByText('Yêu cầu đã tồn tại với nội dung khác.')).length).toBeGreaterThan(0);
  });

  it('surfaces a network/API failure as a recoverable inline error', async () => {
    submitMock.mockRejectedValueOnce(new NetworkError('Không thể kết nối tới máy chủ backend cục bộ.'));

    const user = userEvent.setup();
    render(<TTSPage />);
    await waitForHistoryToSettle();

    await user.click(screen.getByRole('button', { name: /tạo giọng nói/i }));

    expect((await screen.findAllByText('Không thể kết nối tới máy chủ backend cục bộ.')).length).toBeGreaterThan(0);
  });

  it('shows a recoverable error (not stale audio) when a completed job\'s artifact 404s on playback', async () => {
    submitMock.mockResolvedValueOnce({
      job_id: 'job-404-1',
      status: 'COMPLETED',
      audio_url: '/api/audio/job-404-1.wav',
    } satisfies TtsJob);

    const user = userEvent.setup();
    render(<TTSPage />);
    await waitForHistoryToSettle();

    await user.click(screen.getByRole('button', { name: /tạo giọng nói/i }));
    await screen.findByText('Tạo âm thanh thành công');

    const audioEl = document.querySelector('audio')!;
    fireEvent.error(audioEl);

    expect(await screen.findByText('Không thể phát âm thanh')).toBeInTheDocument();
  });

  it('loads persisted history from GET /api/tts/jobs on mount and displays distinguishing status/format info', async () => {
    listMock.mockResolvedValueOnce([
      { job_id: 'hist-completed-aaa', status: 'COMPLETED', audio_url: '/api/audio/hist-completed-aaa.wav' },
      { job_id: 'hist-failed-bbb', status: 'FAILED', error: { code: 'GENERATION_FAILED', message: 'Lỗi' } },
    ] satisfies TtsJob[]);

    render(<TTSPage />);
    await waitForHistoryToSettle();

    // Job ID cells truncate visually but carry the full id as a title attr.
    expect(await screen.findByTitle('hist-completed-aaa')).toBeInTheDocument();
    expect(screen.getByTitle('hist-failed-bbb')).toBeInTheDocument();
    // Distinguishing status text for each row (StatusBadge label = raw status).
    expect(screen.getByText('COMPLETED')).toBeInTheDocument();
    expect(screen.getByText('FAILED')).toBeInTheDocument();
  });

  it('shows an empty state when persisted history has no jobs yet, and does not error', async () => {
    listMock.mockResolvedValueOnce([]);

    render(<TTSPage />);
    await waitForHistoryToSettle();

    expect(await screen.findByText('Chưa có lịch sử Text to Speech')).toBeInTheDocument();
  });

  it('replays a COMPLETED history item through the existing audio endpoint via the modal', async () => {
    listMock.mockResolvedValueOnce([
      { job_id: 'hist-replay-ccc', status: 'COMPLETED', audio_url: '/api/audio/hist-replay-ccc.wav' },
    ] satisfies TtsJob[]);

    const user = userEvent.setup();
    render(<TTSPage />);
    await waitForHistoryToSettle();

    await user.click(await screen.findByRole('button', { name: /phát lại/i }));

    expect(await screen.findByText('Nghe lại âm thanh')).toBeInTheDocument();
    const dialog = screen.getByRole('dialog');
    const audioEl = dialog.querySelector('audio');
    expect(audioEl).toHaveAttribute('src', `${API_ORIGIN}/api/audio/hist-replay-ccc.wav`);
  });

  it('leaves a FAILED history item as FAILED (no replay action) rather than offering to play it', async () => {
    listMock.mockResolvedValueOnce([
      { job_id: 'hist-onlyfail-ddd', status: 'FAILED', error: { code: 'GENERATION_FAILED', message: 'Thất bại' } },
    ] satisfies TtsJob[]);

    render(<TTSPage />);
    await waitForHistoryToSettle();

    await screen.findByTitle('hist-onlyfail-ddd');
    expect(screen.queryByRole('button', { name: /phát lại/i })).not.toBeInTheDocument();
    expect(screen.getByText('GENERATION_FAILED')).toBeInTheDocument();
  });
});
