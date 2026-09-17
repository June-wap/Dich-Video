import React, { useRef, useState } from 'react';
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
  AudioPlayer,
  ErrorState,
} from '../components';
import { useVoiceProfiles } from '../hooks';
import { voiceProfileService } from '../services/voiceProfileService';
import type { VoiceProfile, CloneAudioFormat, CloneTTSResult } from '../services/voiceProfileService';
import { ApiError, NetworkError } from '../services/httpClient';

type CloneWorkflowStage = 'SETUP' | 'PREVIEW';
type HumanReviewState = 'PENDING' | 'ACCEPTED' | 'REJECTED';

// Mirrors backend/services/voice_profile_service.py's real validation
// constants - checked client-side for immediate feedback, but the backend
// remains authoritative (INVALID_REFERENCE_AUDIO / REFERENCE_AUDIO_TOO_LARGE
// / INVALID_REFERENCE_TRANSCRIPT).
const MAX_REFERENCE_SIZE_BYTES = 15 * 1024 * 1024;
const ACCEPTED_AUDIO_EXTENSIONS = ['.wav', '.mp3'];
const MAX_TRANSCRIPT_LENGTH = 2000;
const MAX_TEST_TEXT_LENGTH = 2000;

const LANGUAGES = [
  { value: 'vi', label: 'Vietnamese (Tiếng Việt)' },
  { value: 'en', label: 'English (Tiếng Anh)' },
  { value: 'zh', label: 'Chinese (Tiếng Trung)' },
  { value: 'ja', label: 'Japanese (Tiếng Nhật)' },
];

const FORMATS: { value: CloneAudioFormat; label: string }[] = [
  { value: 'wav', label: 'WAV (không nén, chất lượng gốc)' },
  { value: 'mp3', label: 'MP3 (nén, dung lượng nhỏ)' },
];

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const kb = bytes / 1024;
  if (kb < 1024) return `${kb.toFixed(1)} KB`;
  return `${(kb / 1024).toFixed(2)} MB`;
}

function hasAcceptedExtension(name: string): boolean {
  const lower = name.toLowerCase();
  return ACCEPTED_AUDIO_EXTENSIONS.some((ext) => lower.endsWith(ext));
}

function describeError(err: unknown): string {
  if (err instanceof ApiError) return `${err.message} (${err.code})`;
  if (err instanceof NetworkError) return err.message;
  if (err instanceof Error) return err.message;
  return 'Đã xảy ra lỗi không xác định.';
}

export const VoiceCloningPage: React.FC = () => {
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // Shared, server-persisted profile list (also consumed by LongFormPage's
  // voice picker) - reload() after a successful create() below so both stay
  // in sync without a page refresh.
  const { profiles, loading: profilesLoading, reload: reloadProfiles } = useVoiceProfiles();

  // Workflow stage
  const [stage, setStage] = useState<CloneWorkflowStage>('SETUP');

  // Step 1: Reference Audio (real File, uploaded as multipart/form-data)
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);

  // Step 2: Transcript
  const [transcript, setTranscript] = useState('');

  // Step 3: Voice Info (name is optional server-side; the backend defaults
  // to "Voice Profile {id[:8]}" when omitted)
  const [voiceName, setVoiceName] = useState('');

  // POST /api/voices/profiles (multipart) - single request, no job/poll cycle
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [profile, setProfile] = useState<VoiceProfile | null>(null);

  // "Or use an existing profile" - skips creation entirely
  const [existingProfileId, setExistingProfileId] = useState('');

  // Preview: real test-audio generation (POST .../test - synchronous)
  const [testText, setTestText] = useState(
    'Chào bạn, đây là bản thử nghiệm của mô hình giọng nói nhân bản vừa được hoàn tất.'
  );
  const [testLanguage, setTestLanguage] = useState('vi');
  const [testFormat, setTestFormat] = useState<CloneAudioFormat>('wav');
  const [isGeneratingTest, setIsGeneratingTest] = useState(false);
  const [testError, setTestError] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<CloneTTSResult | null>(null);
  const [playbackError, setPlaybackError] = useState(false);
  const [humanReview, setHumanReview] = useState<HumanReviewState>('PENDING');

  // Validation
  const isAudioValid = Boolean(selectedFile && !fileError);
  const transcriptCharCount = transcript.trim().length;
  const isTranscriptValid = transcriptCharCount > 0 && transcript.length <= MAX_TRANSCRIPT_LENGTH;
  const canCreateProfile = isAudioValid && isTranscriptValid && !creating;

  const handleFilePicked = (file: File | null) => {
    setCreateError(null);
    if (!file) {
      setSelectedFile(null);
      setFileError(null);
      return;
    }
    if (!hasAcceptedExtension(file.name)) {
      setSelectedFile(file);
      setFileError('Định dạng không được hỗ trợ. Vui lòng chọn tệp WAV hoặc MP3.');
      return;
    }
    if (file.size > MAX_REFERENCE_SIZE_BYTES) {
      setSelectedFile(file);
      setFileError(`Tệp quá lớn (${formatBytes(file.size)}). Kích thước tối đa là 15 MB.`);
      return;
    }
    setSelectedFile(file);
    setFileError(null);
  };

  const handleClearFile = () => {
    setSelectedFile(null);
    setFileError(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleCreateVoiceProfile = async () => {
    if (!canCreateProfile || !selectedFile) return;
    setCreating(true);
    setCreateError(null);
    try {
      const created = await voiceProfileService.create({
        file: selectedFile,
        referenceTranscript: transcript.trim(),
        name: voiceName.trim() || null,
      });
      setProfile(created);
      setStage('PREVIEW');
      setTestResult(null);
      setHumanReview('PENDING');
      void reloadProfiles(); // so LongFormPage's voice picker sees it immediately
    } catch (err) {
      setCreateError(describeError(err));
    } finally {
      setCreating(false);
    }
  };

  const handleUseExistingProfile = () => {
    const found = profiles.find((p) => p.profile_id === existingProfileId);
    if (!found) return;
    setProfile(found);
    setStage('PREVIEW');
    setTestResult(null);
    setHumanReview('PENDING');
    setCreateError(null);
  };

  const handleGenerateTestAudio = async () => {
    if (!profile || !testText.trim()) return;
    setIsGeneratingTest(true);
    setTestError(null);
    setPlaybackError(false);
    try {
      const result = await voiceProfileService.synthesizeTest(profile.profile_id, {
        text: testText.trim(),
        language: testLanguage,
        format: testFormat,
      });
      setTestResult(result);
      setHumanReview('PENDING');
    } catch (err) {
      setTestError(describeError(err));
    } finally {
      setIsGeneratingTest(false);
    }
  };

  const handleBackToSetup = () => {
    setStage('SETUP');
    setTestResult(null);
    setTestError(null);
    setHumanReview('PENDING');
  };

  const testAudioUrl = testResult ? voiceProfileService.resolveAudioUrl(testResult) : null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Page Header */}
      <div>
        <h1 style={{ fontSize: '20px', fontWeight: 700, color: 'var(--neutral-900)' }}>
          Voice Cloning (Zero-Shot)
        </h1>
        <p style={{ fontSize: '13px', color: 'var(--neutral-500)', marginTop: '2px' }}>
          Nhân bản đặc trưng giọng nói từ mẫu âm thanh ngắn — Xử lý trên backend cục bộ, không gửi lên đám mây
        </p>
      </div>

      {/* Stepper Progress Ribbon */}
      <div className="ds-steps-header">
        <div className={`ds-step-item ${isAudioValid ? 'ds-step-item--completed' : 'ds-step-item--active'}`}>
          <div className="ds-step-circle">{isAudioValid ? '✓' : '1'}</div>
          <span className="ds-step-title">1. Reference Audio</span>
        </div>
        <div className={`ds-step-divider-line ${isAudioValid ? 'ds-step-divider-line--active' : ''}`} />

        <div className={`ds-step-item ${isTranscriptValid ? 'ds-step-item--completed' : isAudioValid ? 'ds-step-item--active' : ''}`}>
          <div className="ds-step-circle">{isTranscriptValid ? '✓' : '2'}</div>
          <span className="ds-step-title">2. Transcript</span>
        </div>
        <div className={`ds-step-divider-line ${stage === 'PREVIEW' ? 'ds-step-divider-line--active' : ''}`} />

        <div className={`ds-step-item ${stage === 'PREVIEW' ? 'ds-step-item--active' : ''}`}>
          <div className="ds-step-circle">3</div>
          <span className="ds-step-title">3. Preview & Verify</span>
        </div>
      </div>

      {/* ==================================================================
          WIZARD: STEP 1 & 2 (SETUP STAGE)
          ================================================================== */}
      {stage === 'SETUP' && (
        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) 340px', gap: '20px' }}>
          {/* Left Column: Step 1 & Step 2 */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            {/* STEP 1: REFERENCE AUDIO */}
            <Card>
              <CardHeader>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <CardTitle>Bước 1: Reference Audio (Mẫu âm thanh gốc)</CardTitle>
                  <StatusBadge
                    status={isAudioValid ? 'success' : 'neutral'}
                    label={isAudioValid ? 'Đã chọn file' : 'Chưa có file'}
                    size="sm"
                  />
                </div>
                <CardDescription>
                  Tải lên tệp âm thanh giọng nói rõ ràng, độ dài 3–60 giây, không có nhạc nền. Kích thước tối đa 15 MB.
                </CardDescription>
              </CardHeader>

              <CardContent style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".wav,.mp3,audio/wav,audio/mpeg"
                  style={{ display: 'none' }}
                  onChange={(e) => handleFilePicked(e.target.files?.[0] ?? null)}
                />

                {!selectedFile ? (
                  <div className="ds-dropzone" onClick={() => fileInputRef.current?.click()}>
                    <div className="ds-dropzone-icon">
                      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"></path>
                        <path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
                        <line x1="12" y1="19" x2="12" y2="22"></line>
                      </svg>
                    </div>
                    <div>
                      <h4 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--neutral-900)' }}>
                        Nhấn để chọn file âm thanh mẫu
                      </h4>
                      <p style={{ fontSize: '12px', color: 'var(--neutral-500)', marginTop: '4px' }}>
                        Định dạng được chấp nhận: <strong>WAV, MP3</strong>
                      </p>
                    </div>
                    <Button size="sm" variant="outline" onClick={() => fileInputRef.current?.click()}>
                      Duyệt file WAV / MP3
                    </Button>
                  </div>
                ) : (
                  <div className="ds-audio-file-card">
                    <div className="ds-audio-file-info">
                      <div className="ds-audio-file-icon">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon>
                          <path d="M15.54 8.46a5 5 0 0 1 0 7.07"></path>
                        </svg>
                      </div>
                      <div>
                        <span style={{ fontSize: '14px', fontWeight: 600, color: 'var(--neutral-900)' }}>
                          {selectedFile.name}
                        </span>
                        <div style={{ display: 'flex', gap: '12px', fontSize: '12px', color: 'var(--neutral-500)', marginTop: '2px' }}>
                          <span>Kích thước: {formatBytes(selectedFile.size)}</span>
                          {isAudioValid ? (
                            <span style={{ color: 'var(--success-text)', fontWeight: 500 }}>
                              ✓ Sẽ được xác thực (thời lượng, tần số lấy mẫu) khi tạo hồ sơ
                            </span>
                          ) : (
                            <span style={{ color: 'var(--danger-text)', fontWeight: 500 }}>{fileError}</span>
                          )}
                        </div>
                      </div>
                    </div>

                    <Button size="sm" variant="ghost" onClick={handleClearFile}>
                      Thay đổi file
                    </Button>
                  </div>
                )}

                {/* Privacy Notice Banner */}
                <div className="ds-privacy-notice">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
                    <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
                  </svg>
                  <span>
                    <strong>Bảo mật:</strong> Audio được xử lý bởi backend cục bộ trên máy của bạn. Không tải dữ liệu lên máy chủ đám mây.
                  </span>
                </div>
              </CardContent>
            </Card>

            {/* STEP 2: TRANSCRIPT */}
            <Card>
              <CardHeader>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <CardTitle>Bước 2: Transcript (Nội dung văn bản)</CardTitle>
                  <span
                    style={{
                      fontSize: '12px',
                      color: transcript.length > MAX_TRANSCRIPT_LENGTH ? 'var(--danger-text)' : 'var(--neutral-500)',
                      fontFamily: 'var(--font-family-mono)',
                    }}
                  >
                    {transcript.length} / {MAX_TRANSCRIPT_LENGTH} ký tự
                  </span>
                </div>
                <CardDescription>Nội dung chính xác được đọc trong audio mẫu.</CardDescription>
              </CardHeader>

              <CardContent style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                <TextArea
                  aria-label="Nội dung chính xác được đọc trong audio"
                  rows={4}
                  value={transcript}
                  onChange={(e) => setTranscript(e.target.value)}
                  placeholder="Nhập từng từ ngữ được phát âm trong file ghi âm mẫu..."
                  style={{ fontSize: '14px', lineHeight: '1.6' }}
                  error={transcript.length > MAX_TRANSCRIPT_LENGTH ? `Vượt quá ${MAX_TRANSCRIPT_LENGTH} ký tự.` : undefined}
                />

                {transcriptCharCount === 0 ? (
                  <span className="ds-hint">Vui lòng nhập văn bản chính xác khớp với file ghi âm mẫu.</span>
                ) : isTranscriptValid ? (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: 'var(--success-text)' }}>
                    <span>✓ Bản ghi văn bản hợp lệ.</span>
                  </div>
                ) : null}
              </CardContent>
            </Card>
          </div>

          {/* Right Column: Step 3 (Voice Info & Submit) */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            <Card>
              <CardHeader>
                <CardTitle>Bước 3: Voice Info</CardTitle>
                <CardDescription>Thông tin định danh cho voice profile</CardDescription>
              </CardHeader>

              <CardContent style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <Input
                  label="Voice Name (Tên giọng)"
                  placeholder="e.g. Giọng Thầy Minh (Truyền cảm)"
                  value={voiceName}
                  onChange={(e) => setVoiceName(e.target.value)}
                  hint="Tùy chọn - để trống sẽ dùng tên mặc định do hệ thống đặt"
                />

                <div style={{ padding: '10px 12px', background: 'var(--neutral-50)', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)', fontSize: '12px', color: 'var(--neutral-600)', lineHeight: '1.5' }}>
                  <strong>Yêu cầu đầu vào:</strong>
                  <ul style={{ paddingLeft: '16px', marginTop: '4px' }}>
                    <li style={{ color: isAudioValid ? 'var(--success-text)' : 'inherit' }}>
                      {isAudioValid ? '✓' : '•'} File âm thanh WAV / MP3 (≤15MB)
                    </li>
                    <li style={{ color: isTranscriptValid ? 'var(--success-text)' : 'inherit' }}>
                      {isTranscriptValid ? '✓' : '•'} Bản ghi văn bản khớp lời đọc
                    </li>
                  </ul>
                </div>

                {createError && (
                  <ErrorState
                    title="Không thể tạo Voice Profile"
                    message={createError}
                    retryLabel="Thử lại"
                    onRetry={handleCreateVoiceProfile}
                  />
                )}
              </CardContent>

              <CardFooter>
                <Button
                  variant="primary"
                  size="md"
                  style={{ width: '100%' }}
                  disabled={!canCreateProfile}
                  isLoading={creating}
                  loadingText="Đang tải lên và trích xuất đặc trưng âm học..."
                  onClick={handleCreateVoiceProfile}
                >
                  Tạo Voice Profile
                </Button>
              </CardFooter>
            </Card>

            {/* Or use an already-persisted profile instead of creating a new one */}
            <Card>
              <CardHeader>
                <CardTitle>Hoặc dùng hồ sơ đã có</CardTitle>
                <CardDescription>Chọn một voice profile đã lưu để thử nghiệm ngay</CardDescription>
              </CardHeader>
              <CardContent style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                <Select
                  label="Voice Profile"
                  placeholder={profilesLoading ? 'Đang tải danh sách...' : 'Chọn hồ sơ...'}
                  options={profiles.map((p) => ({ value: p.profile_id, label: p.name }))}
                  value={existingProfileId}
                  onChange={(e) => setExistingProfileId(e.target.value)}
                  disabled={profilesLoading || profiles.length === 0}
                  hint={!profilesLoading && profiles.length === 0 ? 'Chưa có voice profile nào được lưu.' : undefined}
                />
                <Button
                  variant="outline"
                  size="md"
                  disabled={!existingProfileId}
                  onClick={handleUseExistingProfile}
                >
                  Dùng hồ sơ này
                </Button>
              </CardContent>
            </Card>
          </div>
        </div>
      )}

      {/* ==================================================================
          PREVIEW & HUMAN CONFIRMATION
          ================================================================== */}
      {stage === 'PREVIEW' && profile && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <Card>
            <CardHeader>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <CardTitle>{profile.name}</CardTitle>
                    <StatusBadge status="success" label={`Status: ${profile.status}`} />
                  </div>
                  <CardDescription style={{ marginTop: '4px' }}>
                    Mô hình giọng Zero-Shot • Provider: <strong>{profile.provider}</strong>
                    {profile.reference && (
                      <>
                        {' '}• Thời lượng mẫu tham chiếu: <strong>{profile.reference.duration_seconds.toFixed(1)}s</strong>
                        {' '}• {profile.reference.sample_rate}Hz / {profile.reference.channels}ch
                      </>
                    )}
                  </CardDescription>
                </div>

                <Button size="sm" variant="outline" onClick={handleBackToSetup}>
                  Quay lại
                </Button>
              </div>
            </CardHeader>

            <CardContent style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              {/* Test Text Prompt & Generate Action */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                <div className="ds-form-group">
                  <label className="ds-label">Văn bản kiểm tra chất lượng giọng nhân bản (Test Prompt)</label>
                  <TextArea
                    aria-label="Test Prompt"
                    rows={3}
                    value={testText}
                    onChange={(e) => setTestText(e.target.value)}
                    error={testText.length > MAX_TEST_TEXT_LENGTH ? `Vượt quá ${MAX_TEST_TEXT_LENGTH} ký tự.` : undefined}
                  />
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                  <Select
                    label="Ngôn ngữ đầu ra của bản thử"
                    options={LANGUAGES}
                    value={testLanguage}
                    onChange={(e) => setTestLanguage(e.target.value)}
                    hint="Hồ sơ giọng không gắn với một ngôn ngữ cố định - chọn ngôn ngữ cho từng bản thử"
                  />
                  <Select
                    label="Định dạng"
                    options={FORMATS}
                    value={testFormat}
                    onChange={(e) => setTestFormat(e.target.value as CloneAudioFormat)}
                  />
                </div>

                <Button
                  variant="primary"
                  size="md"
                  onClick={handleGenerateTestAudio}
                  isLoading={isGeneratingTest}
                  loadingText="Đang tạo..."
                  disabled={!testText.trim() || testText.length > MAX_TEST_TEXT_LENGTH}
                  style={{ alignSelf: 'flex-start' }}
                >
                  Tạo bản thử
                </Button>
              </div>

              {testError && (
                <ErrorState
                  title="Không thể tạo bản thử"
                  message={testError}
                  retryLabel="Thử lại"
                  onRetry={handleGenerateTestAudio}
                />
              )}

              {/* Real Audio Result */}
              {testResult && testAudioUrl && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                  <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--neutral-800)' }}>
                    Bản thử giọng đọc vừa tạo (Synthesized Sample)
                  </span>

                  <AudioPlayer
                    title={`Mẫu giọng thử nghiệm: ${profile.name}`}
                    voice={profile.name}
                    language={LANGUAGES.find((l) => l.value === testResult.language)?.label.split(' (')[0] ?? testResult.language}
                    src={testAudioUrl}
                    format={testResult.format}
                    onError={() => setPlaybackError(true)}
                  />
                  {playbackError && (
                    <ErrorState
                      title="Không thể phát âm thanh"
                      message="Không tải được tệp âm thanh từ máy chủ (có thể đã bị xoá). Bạn có thể tạo lại bản thử."
                      retryLabel="Tạo lại"
                      onRetry={handleGenerateTestAudio}
                    />
                  )}

                  {/* HUMAN REVIEW CONTROLS (Explicit Human Confirmation) */}
                  <div className="ds-human-review-box">
                    <div>
                      <h4 style={{ fontSize: '13px', fontWeight: 600, color: 'var(--neutral-900)' }}>
                        Đánh giá chất lượng của chuyên viên (Human Review)
                      </h4>
                      <p style={{ fontSize: '12px', color: 'var(--neutral-500)', marginTop: '2px' }}>
                        Hệ thống không tự động công nhận độ tương đồng giọng nói. Vui lòng nghe thẩm định và xác nhận thủ công.
                      </p>
                    </div>

                    <div className="ds-human-review-buttons">
                      <button
                        type="button"
                        className={`ds-review-btn ${humanReview === 'ACCEPTED' ? 'ds-review-btn--accepted' : ''}`}
                        onClick={() => setHumanReview('ACCEPTED')}
                      >
                        <span>👍</span>
                        <span>Đúng giọng (Chất lượng đạt chuẩn)</span>
                      </button>

                      <button
                        type="button"
                        className={`ds-review-btn ${humanReview === 'REJECTED' ? 'ds-review-btn--rejected' : ''}`}
                        onClick={() => setHumanReview('REJECTED')}
                      >
                        <span>👎</span>
                        <span>Chưa đạt (Cần điều chỉnh mẫu âm thanh)</span>
                      </button>
                    </div>

                    {humanReview === 'ACCEPTED' && (
                      <span style={{ fontSize: '12px', color: 'var(--success-text)', fontWeight: 500 }}>
                        ✓ Bạn đã xác nhận giọng đọc đạt tiêu chuẩn tương đồng âm sắc.
                      </span>
                    )}

                    {humanReview === 'REJECTED' && (
                      <span style={{ fontSize: '12px', color: 'var(--warning-text)', fontWeight: 500 }}>
                        ⚠ Giọng đọc chưa đạt độ tự nhiên mong muốn. Khuyến nghị thu âm lại mẫu sạch hơn hoặc đổi transcript.
                      </span>
                    )}
                  </div>
                </div>
              )}
            </CardContent>

            <CardFooter style={{ justifyContent: 'space-between' }}>
              <Button variant="ghost" size="md" onClick={handleBackToSetup}>
                Hủy bỏ
              </Button>

              <Button
                variant="primary"
                size="md"
                disabled={!testResult || humanReview !== 'ACCEPTED'}
                onClick={() => navigate('/voices')}
                iconLeft={
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"></path>
                    <polyline points="17 21 17 13 7 13 7 21"></polyline>
                    <polyline points="7 3 7 8 15 8"></polyline>
                  </svg>
                }
              >
                Xong — Xem trong Voice Library
              </Button>
            </CardFooter>
          </Card>
        </div>
      )}
    </div>
  );
};
