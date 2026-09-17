import React, { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
  Button,
  Input,
  Select,
  TextArea,
  StatusBadge,
  ProgressBar,
  AudioPlayer,
  ErrorState,
  EmptyState,
} from '../components';
import { useLongFormJobRunner, useVoiceProfiles } from '../hooks';
import type { LongFormFormPayload } from '../hooks';
import { longFormJobService } from '../services/longFormJobService';
import type { LongFormAudioFormat } from '../services/longFormJobService';

type LongFormScreen = 'EDITOR' | 'PROCESSING' | 'COMPLETED' | 'CANCELLED' | 'ERROR';

// Mirrors backend/schemas/long_form.py LongFormRequest.text (Field(max_length=100000)) -
// deliberately NOT the Short TTS 2,000-char limit (Task 3.5's chunking config
// 240/320/3 is what makes text of this length practical to synthesize).
const MAX_LONG_FORM_TEXT_LENGTH = 100_000;

const LANGUAGES = [
  { value: 'vi', label: 'Tiếng Việt (Vietnamese)' },
  { value: 'en', label: 'Tiếng Anh (English)' },
  { value: 'ja', label: 'Tiếng Nhật (Japanese)' },
  { value: 'zh', label: 'Tiếng Trung (Chinese)' },
];

const FORMATS: { value: LongFormAudioFormat; label: string }[] = [
  { value: 'wav', label: 'WAV (không nén, chất lượng gốc)' },
  { value: 'mp3', label: 'MP3 (nén, dung lượng nhỏ)' },
];

const DEFAULT_TEXT = `Chương 1: Bình minh trên thảo nguyên xanh biếc.

Mặt trời bắt đầu nhô lên khỏi rặng núi phía đông, rải những tia nắng ấm áp đầu tiên xuống thảo nguyên bao la bát ngát. Những giọt sương mai đọng trên ngọn cỏ lấp lánh như hàng vạn viên ngọc bích tuyệt mỹ. Gió sớm khẽ lay động cành lá non, mang theo hương thơm ngai ngái của đất trời vừa thức giấc sau một đêm dài yên bình.

Từ xa xa, tiếng chim sơn ca ríu rít cất lên bài ca đón chào ngày mới. Đàn ngựa của bộ tộc bắt đầu gặm cỏ quanh bờ suối trong vắt, nơi làn nước trong veo phản chiếu sắc trời xanh ngắt. Một cảm giác thanh bình kỳ lạ bao trùm khắp không gian, khiến bất kỳ ai đặt chân đến đây cũng cảm nhận được sự tự do và khoáng đạt vô tận của thiên nhiên.

Người lữ khách dừng chân bên gốc cây cổ thụ ngàn năm, khẽ mỉm cười và hít thở thật sâu luồng không khí thanh sạch. Hành trình dài vượt qua dãy núi tuyết hiểm trở cuối cùng cũng đã đưa anh tới vùng đất hứa - nơi khởi đầu của những truyền thuyết huyền thoại ngàn năm về trước.`;

function languageLabel(code: string): string {
  return LANGUAGES.find((l) => l.value === code)?.label.split(' (')[0] ?? code;
}

/**
 * Screen derivation. `manualEditorReturn` lets the user leave a terminal
 * screen (COMPLETED/CANCELLED/ERROR) and go back to editing without the hook
 * needing an explicit "reset" - the job/requestError the hook holds are
 * simply ignored for screen purposes until a new submit() clears the flag.
 */
function deriveScreen(
  phase: 'idle' | 'submitting' | 'polling' | 'cancelling',
  job: { status: string } | null,
  requestError: { message: string } | null,
  manualEditorReturn: boolean
): LongFormScreen {
  if (phase !== 'idle') return 'PROCESSING';
  if (manualEditorReturn) return 'EDITOR';
  if (!job) return requestError ? 'ERROR' : 'EDITOR';
  if (job.status === 'COMPLETED') return 'COMPLETED';
  if (job.status === 'CANCELLED') return 'CANCELLED';
  if (job.status === 'FAILED') return 'ERROR';
  return 'EDITOR';
}

export const LongFormPage: React.FC = () => {
  const navigate = useNavigate();

  const { profiles, loading: profilesLoading, error: profilesError } = useVoiceProfiles();
  const { job, phase, requestError, isBusy, submit, cancel, canCancel } = useLongFormJobRunner();

  // Local-only label for the current text - NOT sent to the backend
  // (LongFormRequest has model_config = ConfigDict(extra="forbid"), so there
  // is no project-name field to submit it as). Used only to title the
  // Processing/Completed cards below.
  const [projectName, setProjectName] = useState('Chương 1: Bình minh trên thảo nguyên');
  const [text, setText] = useState(DEFAULT_TEXT);
  const [language, setLanguage] = useState('vi');
  const [profileId, setProfileId] = useState('');
  const [format, setFormat] = useState<LongFormAudioFormat>('wav');
  const [formError, setFormError] = useState<string | null>(null);
  const [playbackError, setPlaybackError] = useState(false);
  const [manualEditorReturn, setManualEditorReturn] = useState(false);

  const stats = useMemo(() => {
    const trimmed = text.trim();
    const words = trimmed ? trimmed.split(/\s+/).length : 0;
    const characters = text.length;
    // Rough estimate only (~14 chars/sec) - purely informational, the real
    // duration comes from the completed job's audio.
    const totalSecs = Math.max(0, Math.round(characters / 14));
    const m = Math.floor(totalSecs / 60);
    const s = totalSecs % 60;
    const estDuration = characters > 0 ? `${m} phút ${s} giây` : '0 phút 0 giây';
    return { words, characters, estDuration };
  }, [text]);

  const validate = (): string | null => {
    if (!text.trim()) return 'Vui lòng nhập nội dung văn bản trước khi tạo audio.';
    if (text.length > MAX_LONG_FORM_TEXT_LENGTH) return `Văn bản vượt quá giới hạn ${MAX_LONG_FORM_TEXT_LENGTH.toLocaleString()} ký tự.`;
    if (!profileId) return 'Vui lòng chọn một voice profile trước khi tạo audio.';
    return null;
  };

  const handleStartGeneration = () => {
    const err = validate();
    setFormError(err);
    if (err) return;
    setManualEditorReturn(false);
    const payload: LongFormFormPayload = { text: text.trim(), language, profileId, format };
    void submit(payload);
  };

  const handleCancel = () => {
    void cancel();
  };

  const handleBackToEditor = () => {
    setManualEditorReturn(true);
  };

  const screen = deriveScreen(phase, job, requestError, manualEditorReturn);
  const audioUrl = job ? longFormJobService.resolveAudioUrl(job) : null;
  const resolvedFormat = job ? longFormJobService.guessFormat(job) ?? format : format;
  const progressPercent = job ? Math.round(job.progress_percent) : 0;
  const errorMessage = requestError?.message ?? job?.error?.message;
  const errorCode = requestError?.code ?? job?.error?.code;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* ==================================================================
          1. EDITOR SCREEN
          ================================================================== */}
      {screen === 'EDITOR' && (
        <div className="ds-longform-layout">
          {/* Left: Editor Area */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <Card>
              <CardHeader style={{ gap: '12px' }}>
                <Input
                  label="Tên dự án (chỉ hiển thị cục bộ)"
                  value={projectName}
                  onChange={(e) => setProjectName(e.target.value)}
                  placeholder="Nhập tên bài đọc hoặc tiêu đề sách..."
                />
              </CardHeader>

              <CardContent>
                <div className="ds-form-group">
                  <TextArea
                    aria-label="Nội dung văn bản"
                    value={text}
                    onChange={(e) => {
                      setText(e.target.value);
                      if (formError) setFormError(null);
                    }}
                    placeholder="Dán hoặc nhập toàn bộ nội dung sách, bài viết hoặc tài liệu tại đây..."
                    style={{ minHeight: '340px', fontSize: '14px', lineHeight: '1.7' }}
                    error={
                      text.length > MAX_LONG_FORM_TEXT_LENGTH
                        ? `Vượt quá ${MAX_LONG_FORM_TEXT_LENGTH.toLocaleString()} ký tự.`
                        : undefined
                    }
                  />
                </div>

                <div className="ds-stats-ribbon" style={{ marginTop: '16px' }}>
                  <div className="ds-stat-cell">
                    <span className="ds-stat-number">{stats.words.toLocaleString()}</span>
                    <span className="ds-stat-label">Số từ</span>
                  </div>
                  <div className="ds-stat-divider" />

                  <div className="ds-stat-cell">
                    <span
                      className="ds-stat-number"
                      style={{ color: stats.characters > MAX_LONG_FORM_TEXT_LENGTH ? 'var(--danger-text)' : undefined }}
                    >
                      {stats.characters.toLocaleString()} / {MAX_LONG_FORM_TEXT_LENGTH.toLocaleString()}
                    </span>
                    <span className="ds-stat-label">Số ký tự</span>
                  </div>
                  <div className="ds-stat-divider" />

                  <div className="ds-stat-cell">
                    <span className="ds-stat-number">{stats.estDuration}</span>
                    <span className="ds-stat-label">Thời lượng ước tính</span>
                  </div>
                </div>

                {formError && (
                  <p style={{ fontSize: '12px', color: 'var(--danger-text)', marginTop: '10px' }}>{formError}</p>
                )}
              </CardContent>

              <CardFooter style={{ justifyContent: 'flex-end' }}>
                <Button
                  variant="primary"
                  size="md"
                  onClick={handleStartGeneration}
                  disabled={isBusy}
                  iconLeft={
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <polygon points="5 3 19 12 5 21 5 3"></polygon>
                    </svg>
                  }
                >
                  Tạo audio
                </Button>
              </CardFooter>
            </Card>
          </div>

          {/* Right: Settings Panel */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <Card>
              <CardHeader>
                <CardTitle>Cài đặt giọng đọc</CardTitle>
                <CardDescription>Chọn ngôn ngữ, voice profile và định dạng xuất</CardDescription>
              </CardHeader>
              <CardContent style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <Select
                  label="Ngôn ngữ"
                  options={LANGUAGES}
                  value={language}
                  onChange={(e) => setLanguage(e.target.value)}
                />

                {profiles.length === 0 && !profilesLoading ? (
                  <EmptyState
                    title="Chưa có voice profile"
                    description="Long-form yêu cầu một voice profile đã nhân bản. Tạo một hồ sơ trong Voice Cloning trước."
                    actionLabel="Đến Voice Cloning"
                    onAction={() => navigate('/clone')}
                  />
                ) : (
                  <Select
                    label="Voice Profile"
                    placeholder={profilesLoading ? 'Đang tải danh sách...' : 'Chọn voice profile...'}
                    options={profiles.map((p) => ({ value: p.profile_id, label: p.name }))}
                    value={profileId}
                    onChange={(e) => setProfileId(e.target.value)}
                    disabled={profilesLoading}
                    hint="Long-form chỉ hoạt động với một voice profile đã nhân bản - không có giọng mặc định"
                  />
                )}

                {profilesError && (
                  <span style={{ fontSize: '12px', color: 'var(--danger-text)' }}>
                    Không thể tải danh sách voice profile: {profilesError.message}
                  </span>
                )}

                <Select
                  label="Định dạng xuất"
                  options={FORMATS}
                  value={format}
                  onChange={(e) => setFormat(e.target.value as LongFormAudioFormat)}
                />
              </CardContent>
            </Card>

            <Card>
              <CardContent style={{ padding: '16px', fontSize: '13px', color: 'var(--neutral-600)', lineHeight: '1.6' }}>
                <p>
                  Văn bản dài sẽ được chia thành các đoạn nhỏ và tổng hợp tuần tự trên backend cục bộ. Bạn có thể theo dõi
                  tiến độ thực tế và huỷ bất kỳ lúc nào trong khi đang xử lý.
                </p>
              </CardContent>
            </Card>
          </div>
        </div>
      )}

      {/* ==================================================================
          2. PROCESSING SCREEN — real submit/poll via useLongFormJobRunner
          ================================================================== */}
      {screen === 'PROCESSING' && (
        <div style={{ maxWidth: '640px', margin: '40px auto', width: '100%' }}>
          <Card>
            <CardHeader style={{ textAlign: 'center', paddingBottom: '8px' }}>
              <CardTitle style={{ fontSize: '18px' }}>Đang tạo audio</CardTitle>
              <CardDescription style={{ fontSize: '14px', marginTop: '4px' }}>{projectName}</CardDescription>
            </CardHeader>

            <CardContent style={{ display: 'flex', flexDirection: 'column', gap: '20px', padding: '24px' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '14px', fontWeight: 600, color: 'var(--neutral-900)' }}>
                    {phase === 'submitting'
                      ? 'Đang gửi yêu cầu...'
                      : phase === 'cancelling'
                      ? 'Đang huỷ...'
                      : 'Tiến độ hoàn thành'}
                  </span>
                  {phase === 'polling' && (
                    <span style={{ fontSize: '16px', fontWeight: 700, color: 'var(--color-primary-600)', fontFamily: 'var(--font-family-mono)' }}>
                      {progressPercent}%
                    </span>
                  )}
                </div>
                {phase === 'polling' ? (
                  <ProgressBar value={progressPercent} size="lg" status="default" />
                ) : (
                  <ProgressBar indeterminate size="lg" />
                )}
              </div>

              <p style={{ textAlign: 'center', fontSize: '13px', color: 'var(--neutral-600)', lineHeight: '1.6' }}>
                {phase === 'cancelling'
                  ? 'Đang gửi yêu cầu huỷ - hệ thống chỉ kiểm tra huỷ giữa các đoạn nên có thể mất một chút thời gian.'
                  : 'Hệ thống đang chuyển đổi văn bản thành giọng nói tự nhiên theo từng đoạn, vui lòng đợi trong giây lát...'}
              </p>

              {job && (
                <p style={{ textAlign: 'center', fontSize: '11px', color: 'var(--neutral-400)', fontFamily: 'var(--font-family-mono)' }}>
                  Job ID: {job.job_id}
                </p>
              )}
            </CardContent>

            <CardFooter style={{ justifyContent: 'center', padding: '16px' }}>
              <Button variant="outline" size="md" onClick={handleCancel} disabled={!canCancel}>
                Hủy bỏ
              </Button>
            </CardFooter>
          </Card>
        </div>
      )}

      {/* ==================================================================
          3. COMPLETED SCREEN — real audio via AudioPlayer's src prop
          ================================================================== */}
      {screen === 'COMPLETED' && job && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <Card>
            <CardHeader>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <CardTitle>{projectName}</CardTitle>
                    <StatusBadge status="success" label="Hoàn tất" />
                  </div>
                  <CardDescription style={{ marginTop: '4px' }}>
                    Job ID: <code style={{ fontSize: '12px' }}>{job.job_id}</code>
                  </CardDescription>
                </div>

                <Button size="sm" variant="primary" onClick={handleBackToEditor}>
                  Tạo audio mới
                </Button>
              </div>
            </CardHeader>

            <CardContent style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              {audioUrl ? (
                <AudioPlayer
                  title={projectName}
                  voice={profiles.find((p) => p.profile_id === profileId)?.name || 'Voice profile'}
                  language={languageLabel(language)}
                  src={audioUrl}
                  format={resolvedFormat ?? undefined}
                  onError={() => setPlaybackError(true)}
                />
              ) : (
                <ErrorState title="Thiếu tệp âm thanh" message="Tác vụ đã hoàn tất nhưng không có audio_url trả về từ backend." />
              )}

              {playbackError && (
                <ErrorState
                  title="Không thể phát âm thanh"
                  message="Không tải được tệp âm thanh từ máy chủ (có thể đã bị xoá)."
                />
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {/* ==================================================================
          4. CANCELLED SCREEN
          ================================================================== */}
      {screen === 'CANCELLED' && job && (
        <div style={{ maxWidth: '560px', margin: '40px auto', width: '100%' }}>
          <Card>
            <CardContent style={{ padding: '32px 24px', textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '16px' }}>
              <StatusBadge status="neutral" label="Đã huỷ" />
              <div>
                <h2 style={{ fontSize: '18px', fontWeight: 700, color: 'var(--neutral-900)' }}>Đã huỷ tạo audio.</h2>
                <p style={{ fontSize: '14px', color: 'var(--neutral-600)', marginTop: '6px', lineHeight: '1.5' }}>
                  Bạn đã huỷ tác vụ trước khi hoàn tất. Không có tệp âm thanh nào được tạo.
                </p>
              </div>
              <Button variant="primary" size="md" onClick={handleBackToEditor}>
                Quay lại chỉnh sửa
              </Button>
            </CardContent>
          </Card>
        </div>
      )}

      {/* ==================================================================
          5. ERROR SCREEN
          ================================================================== */}
      {screen === 'ERROR' && (
        <div style={{ maxWidth: '560px', margin: '40px auto', width: '100%' }}>
          <Card>
            <CardContent style={{ padding: '32px 24px', textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '16px' }}>
              <div style={{ width: 48, height: 48, borderRadius: '50%', background: 'var(--danger-bg)', color: 'var(--danger-solid)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="10"></circle>
                  <line x1="12" y1="8" x2="12" y2="12"></line>
                  <line x1="12" y1="16" x2="12.01" y2="16"></line>
                </svg>
              </div>

              <div>
                <h2 style={{ fontSize: '18px', fontWeight: 700, color: 'var(--neutral-900)' }}>Không thể hoàn tất audio.</h2>
                <p style={{ fontSize: '14px', color: 'var(--neutral-600)', marginTop: '6px', lineHeight: '1.5' }}>
                  {errorMessage || 'Đã xảy ra sự cố trong quá trình tạo audio. Bạn có thể thử lại ngay bây giờ hoặc tiếp tục sau.'}
                </p>
                {errorCode && (
                  <code style={{ fontSize: '11px', marginTop: '6px', display: 'inline-block', background: 'rgba(0,0,0,0.05)', padding: '2px 6px', borderRadius: '4px' }}>
                    {errorCode}
                  </code>
                )}
              </div>

              <div style={{ display: 'flex', gap: '12px', marginTop: '8px' }}>
                <Button variant="outline" size="md" onClick={() => navigate('/projects')}>
                  Để sau
                </Button>

                <Button
                  variant="primary"
                  size="md"
                  onClick={handleStartGeneration}
                  iconLeft={
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <polyline points="23 4 23 10 17 10"></polyline>
                      <polyline points="1 20 1 14 7 14"></polyline>
                      <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path>
                    </svg>
                  }
                >
                  Thử lại
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
};
