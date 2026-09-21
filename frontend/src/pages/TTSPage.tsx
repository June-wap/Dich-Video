import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
  Button,
  Select,
  TextArea,
  AudioPlayer,
  GenerationStatus,
  ErrorState,
  StatusBadge,
  DataTable,
  Modal,
  LicenseActivationModal,
} from '../components';
import type { TTSGenerationState } from '../components/GenerationStatus/GenerationStatus';
import type { ColumnDef } from '../components/DataTable/DataTable';
import { useTtsJobRunner, useVoiceProfiles } from '../hooks';
import type { TtsFormPayload } from '../hooks';
import { ttsJobService } from '../services/ttsJobService';
import type { TtsAudioFormat, TtsJob } from '../services/ttsJobService';
import { licenseService, type LicenseStatusResponse } from '../services/licenseService';
import { useAppSettings } from '../context/AppSettingsContext';
import { notify } from '../utils/notifications';
import { PRODUCTION_TTS_LANGUAGES } from '../config/productionLanguages';


// Selecting a cloned voice profile here submits its profile_id as voice_id -
// backend/services/tts_service.py's validate_request()/_run() (updated
// alongside this dropdown) now accepts that as well as the provider's fixed
// built-in voice ids, resolving it through VoiceProfileService and calling
const DEFAULT_VOICE_OPTION_VALUE = '';

const isVietnamese = (value: string) => value.toLowerCase().replace('_', '-') === 'vi' || value.toLowerCase().replace('_', '-') === 'vi-vn';

const FORMATS: { value: TtsAudioFormat; label: string }[] = [
  { value: 'wav', label: 'WAV (không nén, chất lượng gốc)' },
  { value: 'mp3', label: 'MP3 (nén, dung lượng nhỏ)' },
];

// Mirrors backend/services/tts_service.py MAX_TEXT_LENGTH - checked
// client-side for immediate feedback, but the backend remains authoritative.
const MAX_TEXT_LENGTH = 2000;

// Import-from-.txt: a generous cap on the FILE itself (not the resulting
// text) so a user cannot accidentally hand the browser a huge file to decode
// - MAX_TEXT_LENGTH already catches an over-long result afterward via the
// existing character counter/validate(), this just guards the read itself.
const MAX_IMPORT_FILE_SIZE_BYTES = 1 * 1024 * 1024; // 1 MB

const DEFAULT_SAMPLE_TEXT =
  'Xin chào! Chào mừng bạn đến với Voca Basic. Đây là một câu mẫu để tạo giọng nói.';

function languageLabel(code: string): string {
  return PRODUCTION_TTS_LANGUAGES.find((l) => l.value === code)?.label.split(' (')[0] ?? code;
}

/** Displays a cloned profile's name instead of its raw profile_id (a UUID)
 * wherever a submitted voice_id is shown back to the user. Falls back to the
 * id itself if the profile can't be found (e.g. deleted since), so nothing
 * silently disappears. */
function voiceLabel(id: string | null | undefined, profiles: { profile_id: string; name: string }[]): string {
  if (!id) return 'Mặc định';
  return profiles.find((p) => p.profile_id === id)?.name ?? id;
}

/** Maps the job runner's (phase, job, requestError) onto the GenerationStatus
 * component's state, honestly: no fake percentage anywhere, since the
 * backend's TTSStatus carries no progress field at all (see Known
 * Limitations in the Task 3 report). */
function deriveGenerationState(
  phase: 'idle' | 'submitting' | 'polling',
  job: TtsJob | null,
  requestError: { message: string } | null
): TTSGenerationState {
  if (phase === 'submitting') return 'QUEUED';
  if (phase === 'polling') return job?.status === 'RUNNING' ? 'GENERATING' : 'QUEUED';
  if (requestError) return 'ERROR';
  if (job?.status === 'COMPLETED') return 'COMPLETED';
  if (job?.status === 'FAILED') return 'ERROR';
  return 'IDLE';
}

export const TTSPage: React.FC = () => {
  // Form controls
  const [sourceLanguage, setSourceLanguage] = useState('vi');
  const [language, setLanguage] = useState('vi');
  const [voiceId, setVoiceId] = useState('');
  const [format, setFormat] = useState<TtsAudioFormat>('wav');
  const [text, setText] = useState(DEFAULT_SAMPLE_TEXT);
  const [formError, setFormError] = useState<string | null>(null);

  // Settings > Audio > Output Format pre-fills this page's per-job Format
  // dropdown the first time Settings finishes loading - the user can still
  // freely change it per job afterward (this only sets the starting value,
  // it never fights a manual choice). The backend's real /api/tts only
  // accepts exactly "wav" or "mp3" (see backend/schemas/tts.py's
  // TTSData.format Literal and tts_service.py's validate_request()) - there
  // is no actual "produce both" request mode, so Settings' "wav+mp3" choice
  // maps to submitting "mp3" here, which is the closest real backend
  // behavior: whenever fmt=="mp3", TTSService keeps BOTH the original .wav
  // and the exported .mp3 on disk (see tts_service.py's `outputs = [wav_path]
  // + ([mp3_path] if fmt == "mp3" else [])`), it just serves/plays the mp3 as
  // the primary artifact - "wav" alone never produces the extra mp3 copy.
  const { settings: appSettings } = useAppSettings();
  const formatDefaultAppliedRef = useRef(false);
  useEffect(() => {
    if (formatDefaultAppliedRef.current || !appSettings) return;
    formatDefaultAppliedRef.current = true;
    if (appSettings.output_format === 'mp3' || appSettings.output_format === 'wav+mp3') {
      setFormat('mp3');
    } else {
      setFormat('wav');
    }
  }, [appSettings]);

  // Import text from a local .txt file, so a customer can paste in a
  // prepared script instead of retyping/pasting it by hand.
  const txtFileInputRef = useRef<HTMLInputElement | null>(null);
  const handleImportTxt = (file: File | null) => {
    if (!file) return;
    setFormError(null);
    const isTxt = file.name.toLowerCase().endsWith('.txt') || file.type === 'text/plain';
    if (!isTxt) {
      setFormError('Chỉ hỗ trợ nhập từ tệp .txt.');
      return;
    }
    if (file.size > MAX_IMPORT_FILE_SIZE_BYTES) {
      setFormError(`Tệp quá lớn (tối đa ${Math.floor(MAX_IMPORT_FILE_SIZE_BYTES / 1024)} KB cho văn bản).`);
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      const content = typeof reader.result === 'string' ? reader.result : '';
      // Strip a leading UTF-8 BOM (common from Windows Notepad "Save As" ->
      // UTF-8) so it doesn't show up as a stray character at the start of
      // the text area / get read aloud.
      setText(content.replace(/^﻿/, ''));
    };
    reader.onerror = () => {
      setFormError('Không đọc được nội dung tệp. Vui lòng chọn một tệp .txt hợp lệ.');
    };
    reader.readAsText(file, 'utf-8');
  };

  const selectedProfileProvider = isVietnamese(language) ? 'vieneu' : 'chatterbox';
  const canUseCloneProfile = true;

  // Cloned voice profiles (Voice Cloning page) - offered as a dropdown
  // alongside the default voice owned by the selected output language.
  const { profiles: voiceProfiles, loading: voiceProfilesLoading } = useVoiceProfiles();
  const voiceOptions = useMemo(
    () => [
      { value: DEFAULT_VOICE_OPTION_VALUE, label: 'Mặc định (giọng chuẩn của ngôn ngữ)' },
      ...voiceProfiles.filter((p) => p.provider === selectedProfileProvider).map((p) => ({ value: p.profile_id, label: p.name })),
    ],
    [voiceProfiles, selectedProfileProvider]
  );
  // A profile picked before switching to a non-Vietnamese language is
  // already cleared by the effect above; this also covers a profile that
  // was deleted elsewhere (e.g. on /voices) while still selected here.
  useEffect(() => {
    if (canUseCloneProfile && voiceId && !voiceProfilesLoading && !voiceProfiles.some((p) => p.profile_id === voiceId && p.provider === selectedProfileProvider)) {
      setVoiceId('');
    }
  }, [canUseCloneProfile, voiceId, voiceProfiles, voiceProfilesLoading, selectedProfileProvider]);

  const { job, phase, requestError, isBusy, submit, retry, canRetry, cancelTracking, lastPayload } =
    useTtsJobRunner();

  // Latency display only - purely local timing, not a backend-reported value.
  const submitStartRef = useRef<number | null>(null);
  const [latencyMs, setLatencyMs] = useState<number | undefined>(undefined);
  useEffect(() => {
    if (phase === 'submitting') {
      submitStartRef.current = Date.now();
      setLatencyMs(undefined);
    }
  }, [phase]);
  useEffect(() => {
    if (job?.status === 'COMPLETED' && submitStartRef.current) {
      setLatencyMs(Date.now() - submitStartRef.current);
    }
  }, [job]);

  // Playback error (e.g. the completed job's artifact 404s) - reset per job.
  const [playbackError, setPlaybackError] = useState(false);
  useEffect(() => setPlaybackError(false), [job?.job_id]);

  // The backend's TTSStatus does not return the submitted text (job_id,
  // status, audio_url, error only - see backend/schemas/tts.py TTSStatus).
  // This in-memory map enriches jobs created THIS browser session with a
  // text preview for the history table below; it intentionally does not
  // survive a reload, and jobs read back from GET /api/tts/jobs on mount
  // never have an entry here. That is a documented backend contract
  // limitation, not a bug - see the Task 3 report's Known Limitations.
  const textPreviewsRef = useRef<Map<string, { text: string; language: string; voiceId: string | null }>>(new Map());
  useEffect(() => {
    if (job && lastPayload && !textPreviewsRef.current.has(job.job_id)) {
      textPreviewsRef.current.set(job.job_id, {
        text: lastPayload.text,
        language: lastPayload.language,
        voiceId: lastPayload.voiceId,
      });
    }
  }, [job, lastPayload]);

  // History (GET /api/tts/jobs), persisted server-side - survives reload.
  const [history, setHistory] = useState<TtsJob[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [historyError, setHistoryError] = useState<string | null>(null);

  const loadHistory = useCallback(async () => {
    setHistoryLoading(true);
    setHistoryError(null);
    try {
      const items = await ttsJobService.list();
      setHistory([...items].reverse()); // backend returns oldest-first; show newest-first
    } catch (err) {
      setHistoryError(err instanceof Error ? err.message : 'Không thể tải lịch sử.');
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadHistory();
  }, [loadHistory]);

  // Refresh history the moment the active job reaches a terminal state, so
  // it updates without requiring a full page reload.
  const lastSyncedJobIdRef = useRef<string | null>(null);
  useEffect(() => {
    if (job && (job.status === 'COMPLETED' || job.status === 'FAILED') && lastSyncedJobIdRef.current !== job.job_id) {
      lastSyncedJobIdRef.current = job.job_id;
      void loadHistory();
    }
  }, [job, loadHistory]);

  // Settings > General > "Thông báo khi hoàn tất tác vụ" / "Âm báo cảnh báo
  // lỗi" - real browser notifications (see utils/notifications.ts), fired
  // once per job when it reaches a terminal state. Separate ref from
  // lastSyncedJobIdRef above so a notification still fires even if history
  // refresh ever changes independently of this.
  const lastNotifiedJobIdRef = useRef<string | null>(null);
  useEffect(() => {
    if (!job || !appSettings || lastNotifiedJobIdRef.current === job.job_id) return;
    if (job.status === 'COMPLETED') {
      lastNotifiedJobIdRef.current = job.job_id;
      if (appSettings.notify_completion) {
        notify('Text to Speech hoàn tất', `Job ${job.job_id.slice(0, 8)}… đã sẵn sàng để nghe.`);
      }
    } else if (job.status === 'FAILED') {
      lastNotifiedJobIdRef.current = job.job_id;
      if (appSettings.notify_errors) {
        notify('Text to Speech thất bại', job.error?.message || `Job ${job.job_id.slice(0, 8)}… đã thất bại.`);
      }
    }
  }, [job, appSettings]);

  // Replay modal
  const [playingJob, setPlayingJob] = useState<TtsJob | null>(null);
  const [replayError, setReplayError] = useState(false);
  useEffect(() => setReplayError(false), [playingJob?.job_id]);

  const validate = (value: string): string | null => {
    if (!value.trim()) return 'Vui lòng nhập nội dung văn bản trước khi tạo giọng nói.';
    if (value.length > MAX_TEXT_LENGTH) return `Văn bản vượt quá giới hạn ${MAX_TEXT_LENGTH} ký tự.`;
    return null;
  };

  const buildPayload = (): TtsFormPayload => ({
    text: text.trim(),
    sourceLanguage,
    language,
    // Vietnamese baseline has a canonical VieNeu voice. A selected profile
    // UUID replaces it; non-Vietnamese Chatterbox intentionally receives no
    // voice id and selects its own baseline default in the backend.
    voiceId: voiceId.trim() || (isVietnamese(language) ? 'vieneu_default' : null),
    format,
    speed: 1.0, // backend currently only accepts exactly 1.0 - see Known Limitations
  });

  const handleGenerate = () => {
    const err = validate(text);
    setFormError(err);
    if (err) return;
    void submit(buildPayload());
  };

  const handleRetry = () => {
    // Re-attempts the LAST submitted payload (tracked inside the hook) as a
    // fresh operation - not the current form state, which the user may have
    // started editing in the meantime.
    void retry();
  };

  const genState = deriveGenerationState(phase, job, requestError);
  const errorMessage = requestError?.message ?? job?.error?.message;
  const errorCode = requestError?.code ?? job?.error?.code;

  const [licenseData, setLicenseData] = useState<LicenseStatusResponse | null>(null);
  const [licenseModalOpen, setLicenseModalOpen] = useState(false);

  useEffect(() => {
    licenseService.getStatus().then(setLicenseData).catch(() => {});
  }, []);

  useEffect(() => {
    if (errorCode && errorCode.startsWith('LICENSE_')) {
      setLicenseModalOpen(true);
    }
  }, [errorCode]);

  const currentAudioUrl = job ? ttsJobService.resolveAudioUrl(job) : null;
  const currentFormat = job ? ttsJobService.guessFormat(job) ?? format : format;

  const historyColumns: ColumnDef<TtsJob>[] = useMemo(
    () => [
      {
        key: 'job_id',
        header: 'Job ID',
        width: '110px',
        render: (item) => (
          <span
            title={item.job_id}
            style={{ fontFamily: 'var(--font-family-mono)', fontSize: '12px', color: 'var(--neutral-600)' }}
          >
            {item.job_id.slice(0, 8)}…
          </span>
        ),
      },
      {
        key: 'text',
        header: 'Văn bản',
        render: (item) => {
          const preview = textPreviewsRef.current.get(item.job_id);
          return (
            <span
              title={preview?.text}
              style={{
                fontSize: '13px',
                color: 'var(--neutral-800)',
                display: 'block',
                maxWidth: '360px',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {preview ? preview.text : <em style={{ color: 'var(--neutral-400)' }}>(không có bản xem trước)</em>}
            </span>
          );
        },
      },
      {
        key: 'status',
        header: 'Trạng thái',
        width: '120px',
        render: (item) => (
          <StatusBadge
            status={
              item.status === 'COMPLETED'
                ? 'success'
                : item.status === 'FAILED'
                ? 'error'
                : item.status === 'RUNNING'
                ? 'info'
                : 'warning'
            }
            label={item.status}
            size="sm"
          />
        ),
      },
      {
        key: 'format',
        header: 'Định dạng',
        width: '90px',
        render: (item) => {
          const fmt = ttsJobService.guessFormat(item);
          return <span style={{ fontSize: '12px', color: 'var(--neutral-600)' }}>{fmt ? fmt.toUpperCase() : '—'}</span>;
        },
      },
      {
        key: 'actions',
        header: 'Hành động',
        width: '130px',
        align: 'right',
        render: (item) =>
          item.status === 'COMPLETED' && item.audio_url ? (
            <Button size="sm" variant="outline" onClick={() => setPlayingJob(item)}>
              Phát lại
            </Button>
          ) : item.status === 'FAILED' ? (
            <span style={{ fontSize: '12px', color: 'var(--danger-text)' }} title={item.error?.message}>
              {item.error?.code ?? 'FAILED'}
            </span>
          ) : (
            <span style={{ fontSize: '12px', color: 'var(--neutral-400)' }}>—</span>
          ),
      },
    ],
    []
  );

  const charCount = text.length;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* 1. Page Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <h1 style={{ fontSize: '20px', fontWeight: 700, color: 'var(--neutral-900)' }}>Text to Speech</h1>
          <p style={{ fontSize: '13px', color: 'var(--neutral-500)', marginTop: '2px' }}>
            Tổng hợp giọng nói cục bộ (Single Prompt TTS) — Không tốn phí, không gửi dữ liệu ra ngoài
          </p>
        </div>

        <StatusBadge status="neutral" label={`Định dạng: ${format.toUpperCase()}`} size="sm" showDot={false} />
      </div>

      {/* 2. Main 2-Column Desktop Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) 340px', gap: '20px' }}>
        {/* Left Column: Text Editor & Generation Status / Result */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <Card>
            <CardHeader>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <CardTitle>Văn bản cần đọc</CardTitle>
                <span
                  style={{
                    fontSize: '12px',
                    color: charCount > MAX_TEXT_LENGTH ? 'var(--danger-solid)' : 'var(--neutral-500)',
                    fontFamily: 'var(--font-family-mono)',
                  }}
                >
                  {charCount} / {MAX_TEXT_LENGTH} ký tự
                </span>
              </div>
              <CardDescription>
                Nhập văn bản tiếng Việt hoặc ngoại ngữ bạn muốn chuyển đổi thành giọng nói tự nhiên.
              </CardDescription>
            </CardHeader>

            <CardContent>
              <TextArea
                aria-label="Văn bản cần đọc"
                value={text}
                onChange={(e) => {
                  setText(e.target.value);
                  if (formError) setFormError(null);
                }}
                placeholder="Nhập hoặc dán văn bản tại đây..."
                style={{ minHeight: '180px', fontSize: '14px', lineHeight: '1.6' }}
                disabled={isBusy}
                error={formError ?? undefined}
              />
            </CardContent>

            <CardFooter style={{ justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', gap: '10px' }}>
                <input
                  ref={txtFileInputRef}
                  type="file"
                  accept=".txt,text/plain"
                  style={{ display: 'none' }}
                  onChange={(e) => {
                    handleImportTxt(e.target.files?.[0] ?? null);
                    e.target.value = ''; // allow re-selecting the same file
                  }}
                />
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => txtFileInputRef.current?.click()}
                  disabled={isBusy}
                  iconLeft={
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                      <polyline points="17 8 12 3 7 8"></polyline>
                      <line x1="12" y1="3" x2="12" y2="15"></line>
                    </svg>
                  }
                >
                  Nhập từ tệp .txt
                </Button>
                <Button variant="ghost" size="sm" onClick={() => setText('')} disabled={isBusy || !text}>
                  Xóa văn bản
                </Button>
              </div>

              <div style={{ display: 'flex', gap: '10px' }}>
                {isBusy && (
                  <Button variant="outline" size="md" onClick={cancelTracking}>
                    Ẩn tiến trình
                  </Button>
                )}

                <Button
                  variant="primary"
                  size="md"
                  onClick={handleGenerate}
                  isLoading={isBusy}
                  loadingText="Đang xử lý..."
                  iconLeft={
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <polygon points="5 3 19 12 5 21 5 3"></polygon>
                    </svg>
                  }
                >
                  Tạo giọng nói
                </Button>
              </div>
            </CardFooter>
          </Card>

          {/* Generation Status Indicator (skipped while fully idle with no prior attempt) */}
          {(genState !== 'IDLE' || job) && (
            <GenerationStatus
              state={genState}
              latencyMs={latencyMs}
              errorMessage={errorMessage}
              onCancel={isBusy ? cancelTracking : undefined}
            />
          )}

          {/* Completed State: Real Audio Player */}
          {genState === 'COMPLETED' && job && currentAudioUrl && (
            <Card>
              <CardHeader>
                <CardTitle>Kết quả âm thanh đã tạo</CardTitle>
                <CardDescription>
                  Job ID: <code style={{ fontSize: '12px' }}>{job.job_id}</code>
                </CardDescription>
              </CardHeader>
              <CardContent style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                <AudioPlayer
                  title="Kết quả Text to Speech"
                  voice={voiceLabel(voiceId, voiceProfiles)}
                  language={languageLabel(language)}
                  src={currentAudioUrl}
                  format={currentFormat ?? undefined}
                  onRegenerate={handleGenerate}
                  onError={() => setPlaybackError(true)}
                />
                {playbackError && (
                  <ErrorState
                    title="Không thể phát âm thanh"
                    message="Không tải được tệp âm thanh từ máy chủ (có thể đã bị xoá). Bạn có thể tạo lại."
                    retryLabel="Tạo lại"
                    onRetry={handleGenerate}
                  />
                )}
              </CardContent>
            </Card>
          )}

          {/* Error State Banner */}
          {genState === 'ERROR' && (
            <ErrorState
              title="Không thể hoàn thành tổng hợp"
              message={errorMessage || 'Đã xảy ra lỗi không xác định trong quá trình xử lý giọng nói.'}
              details={errorCode}
              retryLabel="Thử lại"
              onRetry={canRetry ? handleRetry : undefined}
            />
          )}
        </div>

        {/* Right Column: Voice & Synthesis Parameters */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <Card>
            <CardHeader>
              <CardTitle>Cấu hình giọng đọc</CardTitle>
              <CardDescription>Ngôn ngữ, định dạng xuất và giọng đọc</CardDescription>
            </CardHeader>

            <CardContent style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <Select
                label="Ngôn ngữ nguồn (Source Language)"
                options={PRODUCTION_TTS_LANGUAGES}
                value={sourceLanguage}
                onChange={(e) => setSourceLanguage(e.target.value)}
                disabled={isBusy}
                hint="Ngôn ngữ của văn bản bạn nhập"
              />

              <Select
                label="Ngôn ngữ đầu ra (Target / Output Language)"
                options={PRODUCTION_TTS_LANGUAGES}
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
                disabled={isBusy}
                hint="Xác định ngôn ngữ giọng đọc đầu ra"
              />

              <Select
                label="Định dạng xuất (Format)"
                options={FORMATS}
                value={format}
                onChange={(e) => setFormat(e.target.value as TtsAudioFormat)}
                disabled={isBusy}
                hint="WAV cho chất lượng gốc, MP3 cho dung lượng nhỏ"
              />

              <Select
                label="Giọng đọc"
                options={voiceOptions}
                value={voiceId || DEFAULT_VOICE_OPTION_VALUE}
                onChange={(e) => setVoiceId(e.target.value === DEFAULT_VOICE_OPTION_VALUE ? '' : e.target.value)}
                disabled={isBusy || voiceProfilesLoading}
                hint={
                  voiceOptions.length > 1
                    ? 'Chọn "Mặc định" hoặc một giọng bạn đã nhân bản ở trang Voice Cloning'
                    : 'Chưa có giọng nhân bản tương thích - tạo ở trang Voice Cloning để chọn tại đây'
                }
              />

              <Select
                label="Tốc độ đọc (Speed)"
                options={[{ value: '1.0', label: '1.0x (cố định)' }]}
                value="1.0"
                disabled
                hint="Backend hiện chỉ hỗ trợ tốc độ 1.0x"
                onChange={() => {}}
              />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Thông số cục bộ</CardTitle>
              <CardDescription>Trạng thái kết nối backend</CardDescription>
            </CardHeader>
            <CardContent style={{ display: 'flex', flexDirection: 'column', gap: '10px', fontSize: '13px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--neutral-600)' }}>
                <span>API:</span>
                <span style={{ fontWeight: 600, color: 'var(--neutral-900)' }}>POST /api/tts/jobs</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--neutral-600)' }}>
                <span>Sample Rate:</span>
                <span style={{ fontWeight: 600, color: 'var(--neutral-900)' }}>24,000 Hz</span>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* 3. TTS History (persisted, GET /api/tts/jobs) */}
      <Card>
        <CardHeader>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
            <div>
              <CardTitle>Lịch sử Text to Speech</CardTitle>
              <CardDescription>Đọc trực tiếp từ backend - vẫn còn sau khi tải lại trang</CardDescription>
            </div>
            <Button size="sm" variant="ghost" onClick={() => void loadHistory()} disabled={historyLoading}>
              Làm mới
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {historyError ? (
            <ErrorState
              title="Không thể tải lịch sử"
              message={historyError}
              retryLabel="Thử lại"
              onRetry={() => void loadHistory()}
            />
          ) : historyLoading ? (
            <div style={{ padding: '24px', textAlign: 'center', fontSize: '13px', color: 'var(--neutral-500)' }}>
              Đang tải lịch sử...
            </div>
          ) : (
            <DataTable
              columns={historyColumns}
              data={history}
              keyExtractor={(item) => item.job_id}
              emptyTitle="Chưa có lịch sử Text to Speech"
              emptyDescription="Các tác vụ bạn tạo ở trên sẽ xuất hiện tại đây, kể cả sau khi tải lại trang."
            />
          )}
        </CardContent>
      </Card>

      {/* Replay Modal */}
      <Modal
        isOpen={Boolean(playingJob)}
        onClose={() => setPlayingJob(null)}
        title="Nghe lại âm thanh"
        size="md"
        footer={
          <Button variant="outline" size="md" onClick={() => setPlayingJob(null)}>
            Đóng
          </Button>
        }
      >
        {playingJob && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <AudioPlayer
              title={`Job ${playingJob.job_id.slice(0, 8)}`}
              voice={voiceLabel(textPreviewsRef.current.get(playingJob.job_id)?.voiceId, voiceProfiles)}
              language={languageLabel(textPreviewsRef.current.get(playingJob.job_id)?.language ?? language)}
              src={ttsJobService.resolveAudioUrl(playingJob) ?? undefined}
              format={ttsJobService.guessFormat(playingJob) ?? undefined}
              onError={() => setReplayError(true)}
            />
            {replayError && (
              <p style={{ fontSize: '12px', color: 'var(--danger-text)' }}>
                Không tìm thấy tệp âm thanh trên máy chủ (có thể đã bị xoá).
              </p>
            )}
          </div>
        )}
      </Modal>
      <LicenseActivationModal
        isOpen={licenseModalOpen}
        onClose={() => setLicenseModalOpen(false)}
        statusData={licenseData}
        onActivated={(status) => setLicenseData(status)}
      />
    </div>
  );
};
