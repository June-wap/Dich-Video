import React, { useState, useEffect, useRef, useMemo } from 'react';
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
} from '../components';
import { useDeveloperMode } from '../hooks';

type LongFormScreen = 'EDITOR' | 'PROCESSING' | 'COMPLETED' | 'ERROR';

const DEFAULT_TEXT = `Chương 1: Bình minh trên thảo nguyên xanh biếc.

Mặt trời bắt đầu nhô lên khỏi rặng núi phía đông, rải những tia nắng ấm áp đầu tiên xuống thảo nguyên bao la bát ngát. Những giọt sương mai đọng trên ngọn cỏ lấp lánh như hàng vạn viên ngọc bích tuyệt mỹ. Gió sớm khẽ lay động cành lá non, mang theo hương thơm ngai ngái của đất trời vừa thức giấc sau một đêm dài yên bình.

Từ xa xa, tiếng chim sơn ca ríu rít cất lên bài ca đón chào ngày mới. Đàn ngựa của bộ tộc bắt đầu gặm cỏ quanh bờ suối trong vắt, nơi làn nước trong veo phản chiếu sắc trời xanh ngắt. Một cảm giác thanh bình kỳ lạ bao trùm khắp không gian, khiến bất kỳ ai đặt chân đến đây cũng cảm nhận được sự tự do và khoáng đạt vô tận của thiên nhiên.

Người lữ khách dừng chân bên gốc cây cổ thụ ngàn năm, khẽ mỉm cười và hít thở thật sâu luồng không khí thanh sạch. Hành trình dài vượt qua dãy núi tuyết hiểm trở cuối cùng cũng đã đưa anh tới vùng đất hứa - nơi khởi đầu của những truyền thuyết huyền thoại ngàn năm về trước.`;

export const LongFormPage: React.FC = () => {
  const navigate = useNavigate();
  const { isDevMode } = useDeveloperMode();

  // Screen State
  const [screen, setScreen] = useState<LongFormScreen>('EDITOR');

  // Customer Editor Fields
  const [projectName, setProjectName] = useState('Chương 1: Bình minh trên thảo nguyên');
  const [activeTab, setActiveTab] = useState<'text' | 'file'>('text');
  const [text, setText] = useState(DEFAULT_TEXT);
  const [language, setLanguage] = useState('vi');
  const [voice, setVoice] = useState('vi-VN-HoaiMy');
  const [quality, setQuality] = useState('balanced');
  const [saveSuccess, setSaveSuccess] = useState(false);

  // Processing state
  const [progressPercent, setProgressPercent] = useState(0);
  const timerRef = useRef<number | null>(null);

  // Stats calculation: Word/character count + Estimated audio duration
  const stats = useMemo(() => {
    const trimmed = text.trim();
    const words = trimmed ? trimmed.split(/\s+/).length : 0;
    const characters = text.length;

    // Estimated audio duration (~14 chars per sec)
    const totalSecs = Math.max(0, Math.round(characters / 14));
    const m = Math.floor(totalSecs / 60);
    const s = totalSecs % 60;
    const estDuration = characters > 0 ? `${m} phút ${s} giây` : '0 phút 0 giây';

    return { words, characters, estDuration, totalSecs: totalSecs || 1122 };
  }, [text]);

  // Handle Start Generation
  const handleStartGeneration = () => {
    setProgressPercent(10);
    setScreen('PROCESSING');

    if (timerRef.current) clearInterval(timerRef.current);

    timerRef.current = window.setInterval(() => {
      setProgressPercent((prev) => {
        if (prev >= 95) {
          if (timerRef.current) clearInterval(timerRef.current);
          timerRef.current = null;
          setScreen('COMPLETED');
          return 100;
        }
        return prev + 15;
      });
    }, 450);
  };

  const handleCancelProcessing = () => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    setProgressPercent(0);
    setScreen('EDITOR');
  };

  const handleSimulateError = () => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    setScreen('ERROR');
  };

  const handleSaveProject = () => {
    setSaveSuccess(true);
    setTimeout(() => setSaveSuccess(false), 2500);
  };

  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>

      {/* Developer Mode Banner (Visible ONLY when Developer Mode is ON under Settings) */}
      {isDevMode && (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 14px', background: 'var(--neutral-100)', border: '1px dashed var(--neutral-400)', borderRadius: 'var(--radius-md)', fontSize: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <StatusBadge status="warning" label="Developer Mode ON" size="sm" />
            <span style={{ color: 'var(--neutral-700)' }}>
              Developer test shortcuts active:
            </span>
            <button
              type="button"
              onClick={() => setScreen('EDITOR')}
              style={{ padding: '2px 8px', fontSize: '11px', cursor: 'pointer', borderRadius: '4px', border: '1px solid var(--border-default)', background: '#fff' }}
            >
              Editor
            </button>
            <button
              type="button"
              onClick={() => { setProgressPercent(68); setScreen('PROCESSING'); }}
              style={{ padding: '2px 8px', fontSize: '11px', cursor: 'pointer', borderRadius: '4px', border: '1px solid var(--border-default)', background: '#fff' }}
            >
              Processing (68%)
            </button>
            <button
              type="button"
              onClick={() => setScreen('COMPLETED')}
              style={{ padding: '2px 8px', fontSize: '11px', cursor: 'pointer', borderRadius: '4px', border: '1px solid var(--border-default)', background: '#fff' }}
            >
              Completed
            </button>
            <button
              type="button"
              onClick={handleSimulateError}
              style={{ padding: '2px 8px', fontSize: '11px', cursor: 'pointer', borderRadius: '4px', border: '1px solid var(--border-default)', background: '#fff', color: 'var(--danger-text)' }}
            >
              Simulate Error
            </button>
          </div>
          <span style={{ color: 'var(--neutral-500)' }}>Internal chunks: 94</span>
        </div>
      )}

      {/* ==================================================================
          1. EDITOR SCREEN (CUSTOMER-FACING)
          ================================================================== */}
      {screen === 'EDITOR' && (
        <div className="ds-longform-layout">
          {/* Left: 70% Editor Area */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <Card>
              <CardHeader style={{ gap: '12px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '12px' }}>
                  <div style={{ flex: 1, minWidth: '260px' }}>
                    <Input
                      label="Tên dự án"
                      value={projectName}
                      onChange={(e) => setProjectName(e.target.value)}
                      placeholder="Nhập tên bài đọc hoặc tiêu đề sách..."
                    />
                  </div>

                  <div className="ds-tabs-list" style={{ marginTop: '16px' }}>
                    <button
                      type="button"
                      className={`ds-tab-trigger ${activeTab === 'text' ? 'ds-tab-trigger--active' : ''}`}
                      onClick={() => setActiveTab('text')}
                    >
                      Nhập văn bản
                    </button>
                    <button
                      type="button"
                      className={`ds-tab-trigger ${activeTab === 'file' ? 'ds-tab-trigger--active' : ''}`}
                      onClick={() => setActiveTab('file')}
                    >
                      Nhập từ file
                    </button>
                  </div>
                </div>
              </CardHeader>

              <CardContent>
                {activeTab === 'text' ? (
                  <div className="ds-form-group">
                    <textarea
                      className="ds-textarea"
                      value={text}
                      onChange={(e) => setText(e.target.value)}
                      placeholder="Dán hoặc nhập toàn bộ nội dung sách, bài viết hoặc tài liệu tại đây..."
                      style={{ minHeight: '340px', fontSize: '14px', lineHeight: '1.7' }}
                    />
                  </div>
                ) : (
                  <div
                    className="ds-dropzone"
                    onClick={() => {
                      setText(DEFAULT_TEXT + '\n\n[Đã nhập nội dung từ tệp tài liệu thành công]');
                      setActiveTab('text');
                    }}
                  >
                    <div className="ds-dropzone-icon">
                      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                        <polyline points="17 8 12 3 7 8"></polyline>
                        <line x1="12" y1="3" x2="12" y2="15"></line>
                      </svg>
                    </div>
                    <div>
                      <h4 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--neutral-900)' }}>
                        Kéo thả tài liệu vào đây hoặc nhấn để duyệt file
                      </h4>
                      <p style={{ fontSize: '12px', color: 'var(--neutral-500)', marginTop: '4px' }}>
                        Hỗ trợ định dạng .TXT, .DOCX, .EPUB, .MD
                      </p>
                    </div>
                    <Button size="sm" variant="outline">
                      Chọn file từ máy tính
                    </Button>
                  </div>
                )}

                {/* Simplified Customer Statistics Ribbon: Only Words, Characters, Estimated Duration */}
                <div className="ds-stats-ribbon" style={{ marginTop: '16px' }}>
                  <div className="ds-stat-cell">
                    <span className="ds-stat-number">{stats.words.toLocaleString()}</span>
                    <span className="ds-stat-label">Số từ</span>
                  </div>
                  <div className="ds-stat-divider" />

                  <div className="ds-stat-cell">
                    <span className="ds-stat-number">{stats.characters.toLocaleString()}</span>
                    <span className="ds-stat-label">Số ký tự</span>
                  </div>
                  <div className="ds-stat-divider" />

                  <div className="ds-stat-cell">
                    <span className="ds-stat-number">{stats.estDuration}</span>
                    <span className="ds-stat-label">Thời lượng ước tính</span>
                  </div>
                </div>
              </CardContent>

              <CardFooter style={{ justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Button variant="outline" size="md" onClick={handleSaveProject}>
                    Lưu dự án
                  </Button>
                  {saveSuccess && (
                    <StatusBadge status="success" label="Đã lưu dự án" size="sm" />
                  )}
                </div>

                <Button
                  variant="primary"
                  size="md"
                  onClick={handleStartGeneration}
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

          {/* Right: 30% Settings Panel (Simplified: Language, Voice, Quality) */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <Card>
              <CardHeader>
                <CardTitle>Cài đặt giọng đọc</CardTitle>
                <CardDescription>Chọn ngôn ngữ, giọng đọc và chất lượng âm thanh</CardDescription>
              </CardHeader>
              <CardContent style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <Select
                  label="Ngôn ngữ"
                  options={[
                    { value: 'vi', label: 'Tiếng Việt (Vietnamese)' },
                    { value: 'en', label: 'Tiếng Anh (English)' },
                    { value: 'ja', label: 'Tiếng Nhật (Japanese)' },
                    { value: 'zh', label: 'Tiếng Trung (Chinese)' },
                  ]}
                  value={language}
                  onChange={(e) => setLanguage(e.target.value)}
                />

                <Select
                  label="Giọng đọc"
                  options={[
                    { value: 'vi-VN-HoaiMy', label: 'Hoài My (Nữ Miền Bắc - Truyền cảm)' },
                    { value: 'vi-VN-NamAnh', label: 'Nam Anh (Nam Miền Bắc - Tự nhiên)' },
                    { value: 'vi-VN-MaiThao', label: 'Mai Thảo (Nữ Miền Nam - Ấm áp)' },
                    { value: 'vi-VN-MinhQuang', label: 'Minh Quang (Nam Miền Nam - Rõ ràng)' },
                  ]}
                  value={voice}
                  onChange={(e) => setVoice(e.target.value)}
                />

                <Select
                  label="Chất lượng âm thanh"
                  options={[
                    { value: 'fast', label: 'Nhanh (Tiết kiệm thời gian)' },
                    { value: 'balanced', label: 'Tự nhiên (Khuyên dùng)' },
                    { value: 'high', label: 'Chất lượng cao (Phòng thu)' },
                  ]}
                  value={quality}
                  onChange={(e) => setQuality(e.target.value)}
                />
              </CardContent>
            </Card>

            <Card>
              <CardContent style={{ padding: '16px', fontSize: '13px', color: 'var(--neutral-600)', lineHeight: '1.6' }}>
                <p>
                  Tất cả các bản âm thanh dài sẽ được xử lý hoàn toàn trên máy tính của bạn với chất lượng đồng đều và bảo mật tuyệt đối.
                </p>
              </CardContent>
            </Card>
          </div>
        </div>
      )}

      {/* ==================================================================
          2. PROCESSING SCREEN (CUSTOMER-FACING)
          ================================================================== */}
      {screen === 'PROCESSING' && (
        <div style={{ maxWidth: '640px', margin: '40px auto', width: '100%' }}>
          <Card>
            <CardHeader style={{ textAlign: 'center', paddingBottom: '8px' }}>
              <CardTitle style={{ fontSize: '18px' }}>Đang tạo audio</CardTitle>
              <CardDescription style={{ fontSize: '14px', marginTop: '4px' }}>
                {projectName}
              </CardDescription>
            </CardHeader>

            <CardContent style={{ display: 'flex', flexDirection: 'column', gap: '20px', padding: '24px' }}>
              {/* Overall percentage & simple progress bar */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '14px', fontWeight: 600, color: 'var(--neutral-900)' }}>
                    Tiến độ hoàn thành
                  </span>
                  <span style={{ fontSize: '16px', fontWeight: 700, color: 'var(--color-primary-600)', fontFamily: 'var(--font-family-mono)' }}>
                    {progressPercent}%
                  </span>
                </div>
                <ProgressBar value={progressPercent} size="lg" status="default" />
              </div>

              {/* Friendly Processing Message */}
              <p style={{ textAlign: 'center', fontSize: '13px', color: 'var(--neutral-600)', lineHeight: '1.6' }}>
                Hệ thống đang chuyển đổi văn bản thành giọng nói tự nhiên, vui lòng đợi trong giây lát...
              </p>

              {/* Developer Mode Collapsed Diagnostics (Visible ONLY when Developer Mode is ON) */}
              {isDevMode && (
                <div style={{ padding: '10px 14px', background: 'var(--neutral-100)', borderRadius: 'var(--radius-md)', fontSize: '11px', color: 'var(--neutral-600)', fontFamily: 'var(--font-family-mono)' }}>
                  <div>[DEV INFO] Internal chunking pipeline active. Current chunk: 68/94.</div>
                  <div>GPU VRAM: 1.8GB / 6.0GB. Model: vi_voice_v1.onnx. RTF: ~0.18.</div>
                </div>
              )}
            </CardContent>

            <CardFooter style={{ justifyContent: 'center', padding: '16px' }}>
              <Button
                variant="outline"
                size="md"
                onClick={handleCancelProcessing}
              >
                Hủy bỏ
              </Button>
            </CardFooter>
          </Card>
        </div>
      )}

      {/* ==================================================================
          3. COMPLETED SCREEN (CUSTOMER-FACING)
          ================================================================== */}
      {screen === 'COMPLETED' && (
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
                    Thời lượng: <strong>{stats.estDuration}</strong> • Giọng đọc: <strong>{voice}</strong>
                  </CardDescription>
                </div>

                <Button
                  size="sm"
                  variant="primary"
                  onClick={() => setScreen('EDITOR')}
                >
                  Tạo audio mới
                </Button>
              </div>
            </CardHeader>

            <CardContent style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              {/* Final Audio Player */}
              <AudioPlayer
                title={projectName}
                duration={stats.totalSecs}
                voice={voice}
                language={language === 'vi' ? 'Tiếng Việt' : language}
                onDownloadWav={() => alert('Đang tải xuống tệp WAV...')}
                onDownloadMp3={() => alert('Đang tải xuống tệp MP3...')}
              />

              {/* Customer Actions */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px', padding: '12px 16px', background: 'var(--neutral-50)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-default)' }}>
                <span style={{ fontSize: '13px', color: 'var(--neutral-700)', fontWeight: 500 }}>
                  Tệp âm thanh hoàn chỉnh đã sẵn sàng để tải về hoặc nghe lại.
                </span>

                <div style={{ display: 'flex', gap: '10px' }}>
                  <Button
                    variant="outline"
                    size="md"
                    onClick={() => alert('Đang tải xuống tệp MP3...')}
                    iconLeft={
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                        <polyline points="7 10 12 15 17 10"></polyline>
                        <line x1="12" y1="15" x2="12" y2="3"></line>
                      </svg>
                    }
                  >
                    Tải MP3
                  </Button>

                  <Button
                    variant="outline"
                    size="md"
                    onClick={() => alert('Đang tải xuống tệp WAV...')}
                    iconLeft={
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                        <polyline points="7 10 12 15 17 10"></polyline>
                        <line x1="12" y1="15" x2="12" y2="3"></line>
                      </svg>
                    }
                  >
                    Tải WAV
                  </Button>

                  <Button
                    variant="primary"
                    size="md"
                    onClick={() => setScreen('EDITOR')}
                  >
                    Tạo audio mới
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* ==================================================================
          4. ERROR SCREEN (FRIENDLY CUSTOMER-FACING)
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
                <h2 style={{ fontSize: '18px', fontWeight: 700, color: 'var(--neutral-900)' }}>
                  Không thể hoàn tất audio.
                </h2>
                <p style={{ fontSize: '14px', color: 'var(--neutral-600)', marginTop: '6px', lineHeight: '1.5' }}>
                  Đã xảy ra sự cố trong quá trình tạo audio. Bạn có thể thử lại ngay bây giờ hoặc tiếp tục sau.
                </p>
              </div>

              {/* Actions: Thử lại, Để sau */}
              <div style={{ display: 'flex', gap: '12px', marginTop: '8px' }}>
                <Button
                  variant="outline"
                  size="md"
                  onClick={() => navigate('/projects')}
                >
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

              {/* Developer Mode Details (ONLY if Developer Mode is explicitly ON) */}
              {isDevMode && (
                <div style={{ marginTop: '16px', padding: '10px 14px', background: 'var(--neutral-100)', borderRadius: 'var(--radius-md)', fontSize: '11px', textAlign: 'left', width: '100%', fontFamily: 'var(--font-family-mono)', color: 'var(--neutral-600)' }}>
                  <div>[DEV ERROR CODE] ERR_INFERENCE_TIMEOUT (Chunk #68)</div>
                  <div>Retries: 2/2. Internal backend trace suppressed.</div>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}

    </div>
  );
};
