import React, { useState, useRef } from 'react';
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
  StatusBadge,
  ProgressBar,
  AudioPlayer,
  ErrorState,
} from '../components';

type CloneWorkflowStage = 'SETUP' | 'CREATING' | 'PREVIEW' | 'SAVED';
type CloneCreationState = 'IDLE' | 'CREATING' | 'READY' | 'FAILED';
type HumanReviewState = 'PENDING' | 'ACCEPTED' | 'REJECTED';

interface ReferenceAudioFile {
  name: string;
  size: string;
  duration: string;
  format: 'WAV' | 'MP3';
  isValid: boolean;
}

const SAMPLE_REFERENCE_AUDIO: ReferenceAudioFile = {
  name: 'reference_sample_speaker_vi.wav',
  size: '2.4 MB',
  duration: '14.2s',
  format: 'WAV',
  isValid: true,
};

const SAMPLE_TRANSCRIPT = 'Xin kính chào quý thính giả, hôm nay chúng ta sẽ cùng tìm hiểu về công nghệ trí tuệ nhân tạo thế hệ mới.';

export const VoiceCloningPage: React.FC = () => {
  const navigate = useNavigate();

  // Workflow Stage
  const [stage, setStage] = useState<CloneWorkflowStage>('SETUP');
  const [creationState, setCreationState] = useState<CloneCreationState>('IDLE');
  const [creationProgress, setCreationProgress] = useState(0);

  // Step 1: Reference Audio
  const [selectedFile, setSelectedFile] = useState<ReferenceAudioFile | null>(null);

  // Step 2: Transcript
  const [transcript, setTranscript] = useState('');

  // Step 3: Voice Info
  const [voiceName, setVoiceName] = useState('');
  const [language, setLanguage] = useState('vi');

  // Preview & Human Review State
  const [testText, setTestText] = useState('Chào bạn, đây là bản thử nghiệm của mô hình giọng nói nhân bản vừa được hoàn tất.');
  const [isGeneratingTestAudio, setIsGeneratingTestAudio] = useState(false);
  const [hasGeneratedTestAudio, setHasGeneratedTestAudio] = useState(false);
  const [humanReview, setHumanReview] = useState<HumanReviewState>('PENDING');

  const creationTimerRef = useRef<number | null>(null);

  // Validation logic
  const isAudioValid = Boolean(selectedFile && selectedFile.isValid);
  const transcriptCharCount = transcript.trim().length;
  const isTranscriptValid = transcriptCharCount >= 10;
  const isVoiceNameValid = voiceName.trim().length >= 3;
  const canCreateProfile = isAudioValid && isTranscriptValid && isVoiceNameValid && creationState !== 'CREATING';

  // Quick preset loader for demonstration / rapid validation
  const handleLoadSample = () => {
    setSelectedFile(SAMPLE_REFERENCE_AUDIO);
    setTranscript(SAMPLE_TRANSCRIPT);
    setVoiceName('Giọng Đọc Mẫu Thảo');
    setLanguage('vi');
  };

  const handleClearFile = () => {
    setSelectedFile(null);
  };

  // Step 3: Start Voice Profile Creation (Simulated)
  const handleCreateVoiceProfile = () => {
    if (!canCreateProfile) return;

    setCreationState('CREATING');
    setCreationProgress(15);

    if (creationTimerRef.current) clearInterval(creationTimerRef.current);

    creationTimerRef.current = window.setInterval(() => {
      setCreationProgress((prev) => {
        if (prev >= 90) {
          if (creationTimerRef.current) clearInterval(creationTimerRef.current);
          creationTimerRef.current = null;
          setCreationProgress(100);
          setCreationState('READY');
          setStage('PREVIEW');
          return 100;
        }
        return prev + 25;
      });
    }, 400);
  };

  const handleSimulateFail = () => {
    if (creationTimerRef.current) clearInterval(creationTimerRef.current);
    setCreationState('FAILED');
  };

  // Preview: Generate Test Audio
  const handleGenerateTestAudio = () => {
    setIsGeneratingTestAudio(true);
    setTimeout(() => {
      setIsGeneratingTestAudio(false);
      setHasGeneratedTestAudio(true);
    }, 1200);
  };

  // Save to Library
  const handleSaveToLibrary = () => {
    setStage('SAVED');
    setTimeout(() => {
      navigate('/voices');
    }, 1500);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Page Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <h1 style={{ fontSize: '20px', fontWeight: 700, color: 'var(--neutral-900)' }}>
            Voice Cloning (Zero-Shot)
          </h1>
          <p style={{ fontSize: '13px', color: 'var(--neutral-500)', marginTop: '2px' }}>
            Nhân bản đặc trưng giọng nói từ mẫu âm thanh ngắn — Xử lý cục bộ 100% không upload lên đám mây
          </p>
        </div>

        {/* Quick Demo Controls */}
        <div style={{ display: 'flex', gap: '8px' }}>
          {stage === 'SETUP' && (
            <Button size="sm" variant="outline" onClick={handleLoadSample}>
              Điền nhanh mẫu test
            </Button>
          )}
          {creationState === 'CREATING' && (
            <Button size="sm" variant="ghost" onClick={handleSimulateFail}>
              Simulate Failure
            </Button>
          )}
        </div>
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
        <div className={`ds-step-divider-line ${isTranscriptValid ? 'ds-step-divider-line--active' : ''}`} />

        <div className={`ds-step-item ${isVoiceNameValid ? 'ds-step-item--completed' : isTranscriptValid ? 'ds-step-item--active' : ''}`}>
          <div className="ds-step-circle">{isVoiceNameValid ? '✓' : '3'}</div>
          <span className="ds-step-title">3. Voice Info</span>
        </div>
        <div className={`ds-step-divider-line ${stage === 'PREVIEW' ? 'ds-step-divider-line--active' : ''}`} />

        <div className={`ds-step-item ${stage === 'PREVIEW' ? 'ds-step-item--active' : ''}`}>
          <div className="ds-step-circle">4</div>
          <span className="ds-step-title">4. Preview & Verify</span>
        </div>
      </div>

      {/* ==================================================================
          WIZARD: STEP 1, 2, 3 (SETUP STAGE)
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
                    status={selectedFile ? 'success' : 'neutral'}
                    label={selectedFile ? 'Đã chọn file' : 'Chưa có file'}
                    size="sm"
                  />
                </div>
                <CardDescription>
                  Tải lên tệp âm thanh giọng nói rõ ràng, khuyến nghị từ 5 đến 30 giây không có nhạc nền.
                </CardDescription>
              </CardHeader>

              <CardContent style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                {!selectedFile ? (
                  <div
                    className="ds-dropzone"
                    onClick={() => setSelectedFile(SAMPLE_REFERENCE_AUDIO)}
                  >
                    <div className="ds-dropzone-icon">
                      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"></path>
                        <path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
                        <line x1="12" y1="19" x2="12" y2="22"></line>
                      </svg>
                    </div>
                    <div>
                      <h4 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--neutral-900)' }}>
                        Kéo thả file âm thanh mẫu vào đây hoặc nhấn để chọn
                      </h4>
                      <p style={{ fontSize: '12px', color: 'var(--neutral-500)', marginTop: '4px' }}>
                        Định dạng được chấp nhận: <strong>WAV, MP3</strong> (Tần số lấy mẫu 16kHz - 48kHz)
                      </p>
                    </div>
                    <Button size="sm" variant="outline">
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
                          <span>Kích thước: {selectedFile.size}</span>
                          <span>Thời lượng: {selectedFile.duration}</span>
                          <span style={{ color: 'var(--success-text)', fontWeight: 500 }}>
                            ✓ Audio hợp lệ (5s–30s)
                          </span>
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
                    <strong>Bảo mật:</strong> Audio được xử lý cục bộ trên thiết bị. Không tải dữ liệu lên bất kỳ máy chủ nào.
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
                      color: isTranscriptValid ? 'var(--neutral-500)' : 'var(--danger-text)',
                      fontFamily: 'var(--font-family-mono)',
                    }}
                  >
                    {transcriptCharCount} ký tự
                  </span>
                </div>
                <CardDescription>
                  Nội dung chính xác được đọc trong audio mẫu.
                </CardDescription>
              </CardHeader>

              <CardContent style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                <div className={`ds-form-group ${!isTranscriptValid && transcriptCharCount > 0 ? 'ds-control--error' : ''}`}>
                  <label className="ds-label ds-label--required">
                    Nội dung chính xác được đọc trong audio
                  </label>
                  <textarea
                    className="ds-textarea"
                    rows={4}
                    value={transcript}
                    onChange={(e) => setTranscript(e.target.value)}
                    placeholder="Nhập từng từ ngữ được phát âm trong file ghi âm mẫu..."
                    style={{ fontSize: '14px', lineHeight: '1.6' }}
                  />
                </div>

                {/* Validation states */}
                {transcriptCharCount === 0 ? (
                  <span className="ds-hint">
                    Vui lòng nhập văn bản chính xác khớp với file ghi âm mẫu.
                  </span>
                ) : isTranscriptValid ? (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: 'var(--success-text)' }}>
                    <span>✓ Bản ghi văn bản hợp lệ và đầy đủ.</span>
                  </div>
                ) : (
                  <span className="ds-error-text">
                    Nội dung quá ngắn. Vui lòng nhập tối thiểu 10 ký tự khớp với file âm thanh.
                  </span>
                )}
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
                  required
                  placeholder="e.g. Giọng Thầy Minh (Truyền cảm)"
                  value={voiceName}
                  onChange={(e) => setVoiceName(e.target.value)}
                  hint="Tên hiển thị trong danh sách Voice Library"
                />

                <Select
                  label="Ngôn ngữ chính (Language)"
                  options={[
                    { value: 'vi', label: 'Vietnamese (Tiếng Việt)' },
                    { value: 'en', label: 'English (Tiếng Anh)' },
                    { value: 'zh', label: 'Chinese (Tiếng Trung)' },
                    { value: 'ja', label: 'Japanese (Tiếng Nhật)' },
                  ]}
                  value={language}
                  onChange={(e) => setLanguage(e.target.value)}
                  hint="Ngôn ngữ của tệp âm thanh tham chiếu"
                />

                <div style={{ padding: '10px 12px', background: 'var(--neutral-50)', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)', fontSize: '12px', color: 'var(--neutral-600)', lineHeight: '1.5' }}>
                  <strong>Yêu cầu đầu vào:</strong>
                  <ul style={{ paddingLeft: '16px', marginTop: '4px' }}>
                    <li style={{ color: isAudioValid ? 'var(--success-text)' : 'inherit' }}>
                      {isAudioValid ? '✓' : '•'} File âm thanh WAV / MP3
                    </li>
                    <li style={{ color: isTranscriptValid ? 'var(--success-text)' : 'inherit' }}>
                      {isTranscriptValid ? '✓' : '•'} Bản ghi văn bản khớp lời đọc
                    </li>
                    <li style={{ color: isVoiceNameValid ? 'var(--success-text)' : 'inherit' }}>
                      {isVoiceNameValid ? '✓' : '•'} Tên giọng nói (tối thiểu 3 ký tự)
                    </li>
                  </ul>
                </div>

                {creationState === 'FAILED' && (
                  <ErrorState
                    title="Không thể trích xuất Voice Profile"
                    message="Không trích xuất được đặc trưng embedding do chất lượng mẫu audio không đồng đều."
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
                  isLoading={creationState === 'CREATING'}
                  loadingText="Đang trích xuất đặc trưng âm học..."
                  onClick={handleCreateVoiceProfile}
                >
                  Tạo Voice Profile
                </Button>
              </CardFooter>
            </Card>

            {/* Creation Progress if in progress */}
            {creationState === 'CREATING' && (
              <Card>
                <CardContent style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px' }}>
                    <span style={{ fontWeight: 600, color: 'var(--color-primary-900)' }}>
                      Trích xuất speaker embedding ({creationProgress}%)
                    </span>
                    <span style={{ color: 'var(--neutral-500)' }}>GPU RTX 4050</span>
                  </div>
                  <ProgressBar value={creationProgress} size="sm" />
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      )}

      {/* ==================================================================
          STAGE 4: CLONE PREVIEW & HUMAN CONFIRMATION
          ================================================================== */}
      {stage === 'PREVIEW' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* Profile Overview Card */}
          <Card>
            <CardHeader>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <CardTitle>{voiceName}</CardTitle>
                    <StatusBadge status="success" label="Status: Ready" />
                  </div>
                  <CardDescription style={{ marginTop: '4px' }}>
                    Mô hình giọng Zero-Shot • Ngôn ngữ: <strong>{language === 'vi' ? 'Vietnamese' : language}</strong> • Thời lượng mẫu tham chiếu: <strong>{selectedFile?.duration || '14.2s'}</strong>
                  </CardDescription>
                </div>

                <Button size="sm" variant="outline" onClick={() => setStage('SETUP')}>
                  Chỉnh sửa mẫu gốc
                </Button>
              </div>
            </CardHeader>

            <CardContent style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              {/* Test Text Prompt & Generate Action */}
              <div className="ds-form-group">
                <label className="ds-label">
                  Văn bản kiểm tra chất lượng giọng nhân bản (Test Prompt)
                </label>
                <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-start' }}>
                  <textarea
                    className="ds-textarea"
                    rows={3}
                    value={testText}
                    onChange={(e) => setTestText(e.target.value)}
                    style={{ flex: 1 }}
                  />
                  <Button
                    variant="primary"
                    size="md"
                    onClick={handleGenerateTestAudio}
                    isLoading={isGeneratingTestAudio}
                    loadingText="Đang tạo..."
                    style={{ marginTop: '2px', whiteSpace: 'nowrap' }}
                  >
                    Tạo bản thử
                  </Button>
                </div>
              </div>

              {/* Mock Audio Result */}
              {hasGeneratedTestAudio && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                  <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--neutral-800)' }}>
                    Bản thử giọng đọc vừa tạo (Synthesized Sample)
                  </span>

                  <AudioPlayer
                    title={`Mẫu giọng thử nghiệm: ${voiceName}`}
                    duration={8.5}
                    voice={voiceName}
                    language={language === 'vi' ? 'Vietnamese' : language}
                  />

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
                        ✓ Bạn đã xác nhận giọng đọc đạt tiêu chuẩn tương đồng âm sắc. Sẵn sàng lưu vào thư viện.
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
              <Button variant="ghost" size="md" onClick={() => setStage('SETUP')}>
                Hủy bỏ
              </Button>

              <Button
                variant="primary"
                size="md"
                disabled={!hasGeneratedTestAudio || humanReview !== 'ACCEPTED'}
                onClick={handleSaveToLibrary}
                iconLeft={
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"></path>
                    <polyline points="17 21 17 13 7 13 7 21"></polyline>
                    <polyline points="7 3 7 8 15 8"></polyline>
                  </svg>
                }
              >
                Lưu vào Voice Library
              </Button>
            </CardFooter>
          </Card>
        </div>
      )}

      {/* SAVED CONFIRMATION MODAL / BANNER */}
      {stage === 'SAVED' && (
        <Card>
          <CardContent style={{ padding: '32px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '16px', textAlign: 'center' }}>
            <div style={{ width: 48, height: 48, borderRadius: '50%', background: 'var(--success-bg)', color: 'var(--success-solid)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polyline points="20 6 9 17 4 12"></polyline>
              </svg>
            </div>
            <div>
              <h3 style={{ fontSize: '18px', fontWeight: 600, color: 'var(--neutral-900)' }}>
                Đã lưu Voice Profile vào Thư viện thành công!
              </h3>
              <p style={{ fontSize: '14px', color: 'var(--neutral-500)', marginTop: '4px' }}>
                Hồ sơ giọng <strong>{voiceName}</strong> đã sẵn sàng để sử dụng trong Text to Speech và Long-form Studio.
              </p>
            </div>
            <Button variant="primary" size="md" onClick={() => navigate('/voices')}>
              Xem Thư viện Voices →
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
};
