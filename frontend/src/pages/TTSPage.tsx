import React, { useState, useRef } from 'react';
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
  Button,
  Select,
  AudioPlayer,
  GenerationStatus,
  ErrorState,
  StatusBadge,
} from '../components';
import type { TTSGenerationState } from '../components/GenerationStatus/GenerationStatus';

interface VoiceOption {
  value: string;
  label: string;
  gender: 'Female' | 'Male';
}

const VOICES_BY_LANG: Record<string, VoiceOption[]> = {
  vi: [
    { value: 'vi-VN-HoaiMy', label: 'Hoài My (Nữ - Giọng Bắc truyền cảm)', gender: 'Female' },
    { value: 'vi-VN-NamAnh', label: 'Nam Anh (Nam - Giọng Bắc tự nhiên)', gender: 'Male' },
    { value: 'vi-VN-MaiThao', label: 'Mai Thảo (Nữ - Giọng Nam ấm áp)', gender: 'Female' },
    { value: 'vi-VN-MinhQuang', label: 'Minh Quang (Nam - Giọng Nam chuẩn)', gender: 'Male' },
  ],
  en: [
    { value: 'en-US-Jenny', label: 'Jenny Studio (Female - Natural US)', gender: 'Female' },
    { value: 'en-US-Guy', label: 'Guy Studio (Male - Confident US)', gender: 'Male' },
    { value: 'en-GB-Sonia', label: 'Sonia Neural (Female - British RP)', gender: 'Female' },
  ],
  zh: [
    { value: 'zh-CN-Xiaoxiao', label: 'Xiaoxiao (Female - Mandarin Standard)', gender: 'Female' },
    { value: 'zh-CN-Yunxi', label: 'Yunxi (Male - Mandarin Warm)', gender: 'Male' },
  ],
  ja: [
    { value: 'ja-JP-Nanami', label: 'Nanami (Female - Tokyo Standard)', gender: 'Female' },
    { value: 'ja-JP-Keita', label: 'Keita (Male - Standard News)', gender: 'Male' },
  ],
  es: [
    { value: 'es-ES-Elvira', label: 'Elvira (Female - Castilian)', gender: 'Female' },
    { value: 'es-MX-Jorge', label: 'Jorge (Male - Mexican Spanish)', gender: 'Male' },
  ],
  pt: [
    { value: 'pt-BR-Francisca', label: 'Francisca (Female - Brazilian)', gender: 'Female' },
    { value: 'pt-BR-Antonio', label: 'Antonio (Male - Brazilian)', gender: 'Male' },
  ],
  it: [
    { value: 'it-IT-Elsa', label: 'Elsa (Female - Standard Italian)', gender: 'Female' },
    { value: 'it-IT-Diego', label: 'Diego (Male - Standard Italian)', gender: 'Male' },
  ],
  fr: [
    { value: 'fr-FR-Denise', label: 'Denise (Female - Parisian French)', gender: 'Female' },
    { value: 'fr-FR-Henri', label: 'Henri (Male - Clear Articulation)', gender: 'Male' },
  ],
  hi: [
    { value: 'hi-IN-Swara', label: 'Swara (Female - Hindi Natural)', gender: 'Female' },
    { value: 'hi-IN-Madhur', label: 'Madhur (Male - Hindi Standard)', gender: 'Male' },
  ],
};

const LANGUAGES = [
  { value: 'vi', label: 'Vietnamese (Tiếng Việt)' },
  { value: 'en', label: 'English (Tiếng Anh)' },
  { value: 'zh', label: 'Chinese (Tiếng Trung)' },
  { value: 'ja', label: 'Japanese (Tiếng Nhật)' },
  { value: 'es', label: 'Spanish (Tây Ban Nha)' },
  { value: 'pt', label: 'Portuguese (Bồ Đào Nha)' },
  { value: 'it', label: 'Italian (Tiếng Ý)' },
  { value: 'fr', label: 'French (Tiếng Pháp)' },
  { value: 'hi', label: 'Hindi (Tiếng Hindi)' },
];

const QUALITIES = [
  { value: 'fast', label: 'Fast (Tốc độ cao - Tiết kiệm tài nguyên)' },
  { value: 'balanced', label: 'Balanced (Cân bằng tự nhiên - Khuyên dùng)' },
  { value: 'high', label: 'High Quality (Chất lượng phòng thu Studio)' },
];

const SPEEDS = [
  { value: '0.5', label: '0.5x' },
  { value: '0.75', label: '0.75x' },
  { value: '1.0', label: '1.0x (Chuẩn)' },
  { value: '1.25', label: '1.25x' },
  { value: '1.5', label: '1.5x' },
  { value: '2.0', label: '2.0x' },
];

const DEFAULT_SAMPLE_TEXT = `Xin chào! Chào mừng bạn đến với OmniVoice Local AI Voice Studio. Đây là phần mềm tổng hợp giọng nói trí tuệ nhân tạo chạy hoàn toàn offline trên máy tính của bạn với card đồ họa RTX 4050, bảo mật dữ liệu tuyệt đối và không phát sinh chi phí API.`;

export const TTSPage: React.FC = () => {
  // Form controls
  const [language, setLanguage] = useState('vi');
  const [voice, setVoice] = useState('vi-VN-HoaiMy');
  const [quality, setQuality] = useState('balanced');
  const [speed, setSpeed] = useState('1.0');
  const [text, setText] = useState(DEFAULT_SAMPLE_TEXT);

  // Generation state machine
  const [genState, setGenState] = useState<TTSGenerationState>('IDLE');
  const [genProgress, setGenProgress] = useState(0);
  const [genLatency, setGenLatency] = useState<number | undefined>(undefined);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Mock audio details
  const [generatedAudio, setGeneratedAudio] = useState<{
    duration: number;
    voice: string;
    language: string;
  } | null>(null);

  const timerRef = useRef<number | null>(null);

  // Handle language change: reset voice to first available for that language
  const handleLanguageChange = (newLang: string) => {
    setLanguage(newLang);
    const available = VOICES_BY_LANG[newLang] || [];
    if (available.length > 0) {
      setVoice(available[0].value);
    }
  };

  // Mock generation trigger
  const handleGenerate = () => {
    if (!text.trim()) {
      setErrorMessage('Vui lòng nhập nội dung văn bản trước khi tạo giọng nói.');
      setGenState('ERROR');
      return;
    }

    // Clear previous timer
    if (timerRef.current) clearInterval(timerRef.current);

    setErrorMessage(null);
    setGenState('GENERATING');
    setGenProgress(10);

    const startTime = Date.now();

    // Simulate progressive generation chunks
    timerRef.current = window.setInterval(() => {
      setGenProgress((prev) => {
        if (prev >= 95) {
          if (timerRef.current) clearInterval(timerRef.current);
          timerRef.current = null;

          const latency = Date.now() - startTime;
          setGenLatency(latency);
          setGenProgress(100);
          setGenState('COMPLETED');

          // Estimate duration based on text length (~15 characters per second)
          const estDuration = Math.max(3.5, Math.round((text.length / 14) * 10) / 10);
          const langObj = LANGUAGES.find((l) => l.value === language);
          setGeneratedAudio({
            duration: estDuration,
            voice,
            language: langObj ? langObj.label.split(' ')[0] : 'Vietnamese',
          });
          return 100;
        }
        return prev + 25;
      });
    }, 250);
  };

  const handleCancel = () => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    setGenState('IDLE');
    setGenProgress(0);
  };

  const handleSimulateError = () => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    setErrorMessage('Mô phỏng lỗi: Không thể cấp phát GPU VRAM hoặc bộ đệm âm thanh bị gián đoạn.');
    setGenState('ERROR');
  };

  const currentVoiceOptions = VOICES_BY_LANG[language] || [];
  const charCount = text.length;
  const maxCharLimit = 5000;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* 1. Page Header & Quick Diagnostics */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <h1 style={{ fontSize: '20px', fontWeight: 700, color: 'var(--neutral-900)' }}>
            Text to Speech
          </h1>
          <p style={{ fontSize: '13px', color: 'var(--neutral-500)', marginTop: '2px' }}>
            Tổng hợp giọng nói cục bộ (Single Prompt TTS) — Không tốn phí, không gửi dữ liệu ra ngoài
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <StatusBadge status="success" label="Local Core: Ready" size="sm" />
          <StatusBadge status="neutral" label="GPU: RTX 4050" size="sm" showDot={false} />
          <Button
            size="sm"
            variant="ghost"
            onClick={handleSimulateError}
            title="Kiểm tra trạng thái lỗi giao diện"
          >
            Simulate Error
          </Button>
        </div>
      </div>

      {/* 2. Main 2-Column Desktop Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) 340px', gap: '20px' }}>
        {/* Left Column: Text Editor & Generation Status / Result */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* Text Editor Card */}
          <Card>
            <CardHeader>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <CardTitle>Văn bản cần đọc</CardTitle>
                <span
                  style={{
                    fontSize: '12px',
                    color: charCount > maxCharLimit ? 'var(--danger-solid)' : 'var(--neutral-500)',
                    fontFamily: 'var(--font-family-mono)',
                  }}
                >
                  {charCount} / {maxCharLimit} ký tự
                </span>
              </div>
              <CardDescription>
                Nhập văn bản tiếng Việt hoặc ngoại ngữ bạn muốn chuyển đổi thành giọng nói tự nhiên.
              </CardDescription>
            </CardHeader>

            <CardContent>
              <div className="ds-form-group">
                <textarea
                  className="ds-textarea"
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  placeholder="Nhập hoặc dán văn bản tại đây..."
                  style={{ minHeight: '180px', fontSize: '14px', lineHeight: '1.6' }}
                  disabled={genState === 'GENERATING'}
                />
              </div>
            </CardContent>

            <CardFooter style={{ justifyContent: 'space-between' }}>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setText('')}
                disabled={genState === 'GENERATING' || !text}
              >
                Xóa văn bản
              </Button>

              <div style={{ display: 'flex', gap: '10px' }}>
                {genState === 'GENERATING' && (
                  <Button variant="outline" size="md" onClick={handleCancel}>
                    Hủy bỏ
                  </Button>
                )}

                <Button
                  variant="primary"
                  size="md"
                  onClick={handleGenerate}
                  isLoading={genState === 'GENERATING'}
                  loadingText="Đang tạo giọng nói..."
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

          {/* Generation Status Indicator */}
          <GenerationStatus
            state={genState}
            progress={genProgress}
            latencyMs={genLatency}
            errorMessage={errorMessage || undefined}
            onCancel={handleCancel}
          />

          {/* Completed State: Mock Audio Player */}
          {genState === 'COMPLETED' && generatedAudio && (
            <Card>
              <CardHeader>
                <CardTitle>Kết quả âm thanh đã tạo</CardTitle>
                <CardDescription>
                  Tệp âm thanh được kết xuất cục bộ. Bạn có thể nghe thử hoặc xuất định dạng WAV / MP3.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <AudioPlayer
                  title="OmniVoice TTS Result"
                  duration={generatedAudio.duration}
                  voice={generatedAudio.voice}
                  language={generatedAudio.language}
                  onRegenerate={handleGenerate}
                />
              </CardContent>
            </Card>
          )}

          {/* Error State Banner if applicable */}
          {genState === 'ERROR' && (
            <ErrorState
              title="Không thể hoàn thành tổng hợp"
              message={errorMessage || 'Đã xảy ra lỗi không xác định trong quá trình xử lý giọng nói.'}
              details="ErrorCode: ERR_TTS_SIMULATED_LOCAL_FAIL"
              retryLabel="Thử lại ngay"
              onRetry={handleGenerate}
            />
          )}
        </div>

        {/* Right Column: Voice & Synthesis Parameters */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <Card>
            <CardHeader>
              <CardTitle>Cấu hình giọng đọc</CardTitle>
              <CardDescription>Ngôn ngữ, mô hình giọng và tốc độ phát</CardDescription>
            </CardHeader>

            <CardContent style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {/* 1. Language Control */}
              <Select
                label="Ngôn ngữ (Language)"
                options={LANGUAGES}
                value={language}
                onChange={(e) => handleLanguageChange(e.target.value)}
                disabled={genState === 'GENERATING'}
                hint="Hỗ trợ 9 ngôn ngữ chuẩn bản địa"
              />

              {/* 2. Voice Control */}
              <Select
                label="Giọng đọc (Voice)"
                options={currentVoiceOptions.map((v) => ({
                  value: v.value,
                  label: `${v.label} [${v.gender}]`,
                }))}
                value={voice}
                onChange={(e) => setVoice(e.target.value)}
                disabled={genState === 'GENERATING'}
                hint="Mô hình giọng nói cục bộ (Offline)"
              />

              {/* 3. Quality Control */}
              <Select
                label="Chất lượng (Quality)"
                options={QUALITIES}
                value={quality}
                onChange={(e) => setQuality(e.target.value)}
                disabled={genState === 'GENERATING'}
                hint="Cân bằng giữa tốc độ tạo và độ tự nhiên"
              />

              {/* 4. Speed Control (0.5x - 2.0x) */}
              <Select
                label="Tốc độ đọc (Speed)"
                options={SPEEDS}
                value={speed}
                onChange={(e) => setSpeed(e.target.value)}
                disabled={genState === 'GENERATING'}
                hint="Điều chỉnh nhịp điệu phát âm từ 0.5x đến 2.0x"
              />
            </CardContent>
          </Card>

          {/* Model Specification Card */}
          <Card>
            <CardHeader>
              <CardTitle>Thông số cục bộ</CardTitle>
              <CardDescription>Trạng thái tài nguyên máy trạm</CardDescription>
            </CardHeader>
            <CardContent style={{ display: 'flex', flexDirection: 'column', gap: '10px', fontSize: '13px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--neutral-600)' }}>
                <span>Backend Provider:</span>
                <span style={{ fontWeight: 600, color: 'var(--neutral-900)' }}>OmniVoice Mock v1</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--neutral-600)' }}>
                <span>Sample Rate:</span>
                <span style={{ fontWeight: 600, color: 'var(--neutral-900)' }}>24,000 Hz</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--neutral-600)' }}>
                <span>Độ trễ dự kiến:</span>
                <span style={{ fontWeight: 600, color: 'var(--neutral-900)' }}>~1.2s – 1.8s</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--neutral-600)' }}>
                <span>Bộ nhớ VRAM:</span>
                <span style={{ fontWeight: 600, color: 'var(--neutral-900)' }}>1.8 GB / 6.0 GB</span>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
};
