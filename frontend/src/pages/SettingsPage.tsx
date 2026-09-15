import React, { useState } from 'react';
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
} from '../components';
import { useDeveloperMode } from '../hooks';

type SettingsTab = 'general' | 'audio' | 'performance' | 'storage' | 'advanced';

export const SettingsPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<SettingsTab>('general');
  const [saveSuccess, setSaveSuccess] = useState(false);

  // General settings state
  const [appLang, setAppLang] = useState('vi');
  const [appTheme, setAppTheme] = useState('light');
  const [notifyCompletion, setNotifyCompletion] = useState(true);
  const [notifyErrors, setNotifyErrors] = useState(true);
  const [checkingUpdate, setCheckingUpdate] = useState(false);
  const [updateStatus, setUpdateStatus] = useState<string | null>(null);

  // Audio settings state
  const [outputFormat, setOutputFormat] = useState('wav+mp3');
  const [pausePolicy, setPausePolicy] = useState('400');
  const [silenceTrim, setSilenceTrim] = useState(true);
  const [outputDir, setOutputDir] = useState('D:\\Tool Dich Cho Khach\\output\\audio');

  // Performance settings state
  const [device, setDevice] = useState<'gpu' | 'cpu'>('gpu');
  const [qualityPreset, setQualityPreset] = useState('balanced');
  const [retryCount, setRetryCount] = useState('2');

  // Advanced / Developer settings state (Defaults to OFF)
  const { isDevMode, setDevMode } = useDeveloperMode();
  const [numSteps, setNumSteps] = useState('16');
  const [sqliteWal, setSqliteWal] = useState(true);
  const [debugLogs, setDebugLogs] = useState(false);

  // Storage settings state
  const [dbPath, setDbPath] = useState('D:\\Tool Dich Cho Khach\\storage\\omnivoice.db');
  const [cacheSize, setCacheSize] = useState('348 MB');
  const [isClearingCache, setIsClearingCache] = useState(false);

  const handleSaveSettings = () => {
    setSaveSuccess(true);
    setTimeout(() => setSaveSuccess(false), 2500);
  };

  const handleCheckUpdate = () => {
    setCheckingUpdate(true);
    setTimeout(() => {
      setCheckingUpdate(false);
      setUpdateStatus('Bạn đang sử dụng phiên bản mới nhất (v0.3.0-alpha).');
    }, 1200);
  };

  const handleClearCache = () => {
    setIsClearingCache(true);
    setTimeout(() => {
      setIsClearingCache(false);
      setCacheSize('0 MB');
    }, 1000);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Top Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h1 style={{ fontSize: '20px', fontWeight: 700, color: 'var(--neutral-900)' }}>
            Settings (Cài đặt hệ thống)
          </h1>
          <p style={{ fontSize: '13px', color: 'var(--neutral-500)', marginTop: '2px' }}>
            Cấu hình giao diện, phần cứng CUDA, tham số âm thanh và đường dẫn lưu trữ
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {saveSuccess && (
            <StatusBadge status="success" label="Đã lưu cài đặt" size="sm" />
          )}
          <Button variant="primary" size="md" onClick={handleSaveSettings}>
            Lưu thay đổi
          </Button>
        </div>
      </div>

      {/* Main Settings Layout: Left Nav + Right Panel */}
      <div className="ds-settings-layout">
        {/* Left Navigation */}
        <nav className="ds-settings-nav">
          <button
            type="button"
            className={`ds-settings-nav-btn ${activeTab === 'general' ? 'ds-settings-nav-btn--active' : ''}`}
            onClick={() => setActiveTab('general')}
          >
            <span>General (Chung)</span>
          </button>

          <button
            type="button"
            className={`ds-settings-nav-btn ${activeTab === 'audio' ? 'ds-settings-nav-btn--active' : ''}`}
            onClick={() => setActiveTab('audio')}
          >
            <span>Audio (Âm thanh)</span>
          </button>

          <button
            type="button"
            className={`ds-settings-nav-btn ${activeTab === 'performance' ? 'ds-settings-nav-btn--active' : ''}`}
            onClick={() => setActiveTab('performance')}
          >
            <span>Performance (Hiệu năng)</span>
          </button>

          <button
            type="button"
            className={`ds-settings-nav-btn ${activeTab === 'storage' ? 'ds-settings-nav-btn--active' : ''}`}
            onClick={() => setActiveTab('storage')}
          >
            <span>Storage (Lưu trữ)</span>
          </button>

          <button
            type="button"
            className={`ds-settings-nav-btn ${activeTab === 'advanced' ? 'ds-settings-nav-btn--active' : ''}`}
            onClick={() => setActiveTab('advanced')}
          >
            <span>Advanced (Nâng cao)</span>
          </button>
        </nav>

        {/* Right Content Panel */}
        <div className="ds-settings-content">

          {/* ================================================================
              TAB: GENERAL
              ================================================================ */}
          {activeTab === 'general' && (
            <Card>
              <CardHeader>
                <CardTitle>Cài đặt chung (General)</CardTitle>
                <CardDescription>Ngôn ngữ giao diện, chủ đề và thông báo người dùng</CardDescription>
              </CardHeader>

              <CardContent style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                <Select
                  label="Ngôn ngữ ứng dụng (Language)"
                  options={[
                    { value: 'vi', label: 'Tiếng Việt (Mặc định)' },
                    { value: 'en', label: 'English (US)' },
                  ]}
                  value={appLang}
                  onChange={(e) => setAppLang(e.target.value)}
                  hint="Ngôn ngữ hiển thị trên thanh menu, bảng điều khiển và nhãn tính năng."
                />

                <Select
                  label="Giao diện hiển thị (Theme)"
                  options={[
                    { value: 'light', label: 'Desktop Light (Workspace sáng chuẩn SaaS)' },
                    { value: 'dark', label: 'Dark Navy (Thanh bên tối)' },
                    { value: 'system', label: 'Đồng bộ hệ điều hành Windows' },
                  ]}
                  value={appTheme}
                  onChange={(e) => setAppTheme(e.target.value)}
                  hint="Tối ưu độ tương phản cho màn hình làm việc lâu dài."
                />

                <div style={{ display: 'flex', flexDirection: 'column', borderTop: '1px solid var(--border-subtle)', paddingTop: '16px' }}>
                  <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--neutral-900)', marginBottom: '8px' }}>
                    Thông báo & Âm thanh
                  </span>

                  <div className="ds-toggle-row">
                    <div>
                      <strong style={{ fontSize: '13px', color: 'var(--neutral-800)', display: 'block' }}>
                        Thông báo khi hoàn tất tác vụ dài
                      </strong>
                      <span style={{ fontSize: '12px', color: 'var(--neutral-500)' }}>
                        Hiển thị thông báo Windows khi hoàn thành sách nói hoặc file âm thanh lớn.
                      </span>
                    </div>
                    <label className="ds-switch">
                      <input
                        type="checkbox"
                        checked={notifyCompletion}
                        onChange={(e) => setNotifyCompletion(e.target.checked)}
                      />
                      <span className="ds-switch-slider" />
                    </label>
                  </div>

                  <div className="ds-toggle-row">
                    <div>
                      <strong style={{ fontSize: '13px', color: 'var(--neutral-800)', display: 'block' }}>
                        Âm báo cảnh báo lỗi
                      </strong>
                      <span style={{ fontSize: '12px', color: 'var(--neutral-500)' }}>
                        Phát âm thanh cảnh báo ngắn nếu phân đoạn xử lý bị gián đoạn.
                      </span>
                    </div>
                    <label className="ds-switch">
                      <input
                        type="checkbox"
                        checked={notifyErrors}
                        onChange={(e) => setNotifyErrors(e.target.checked)}
                      />
                      <span className="ds-switch-slider" />
                    </label>
                  </div>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', borderTop: '1px solid var(--border-subtle)', paddingTop: '16px', gap: '8px' }}>
                  <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--neutral-900)' }}>
                    Kiểm tra bản cập nhật
                  </span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <Button
                      variant="outline"
                      size="sm"
                      isLoading={checkingUpdate}
                      onClick={handleCheckUpdate}
                    >
                      Kiểm tra bản mới
                    </Button>
                    <span style={{ fontSize: '12px', color: 'var(--neutral-500)' }}>
                      Phiên bản hiện tại: <strong>v0.3.0-alpha (Prototype)</strong>
                    </span>
                  </div>
                  {updateStatus && (
                    <span style={{ fontSize: '12px', color: 'var(--success-text)', fontWeight: 500 }}>
                      ✓ {updateStatus}
                    </span>
                  )}
                </div>
              </CardContent>
            </Card>
          )}

          {/* ================================================================
              TAB: AUDIO
              ================================================================ */}
          {activeTab === 'audio' && (
            <Card>
              <CardHeader>
                <CardTitle>Cài đặt âm thanh (Audio)</CardTitle>
                <CardDescription>Định dạng xuất tệp, tần số lấy mẫu và căn chỉnh khoảng lặng</CardDescription>
              </CardHeader>

              <CardContent style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                <Select
                  label="Định dạng xuất (Output Format)"
                  options={[
                    { value: 'wav', label: 'WAV (Lossless 24kHz Uncompressed)' },
                    { value: 'mp3', label: 'MP3 (Lossy 320kbps Compressed)' },
                    { value: 'wav+mp3', label: 'WAV + MP3 (Xuất đồng thời cả 2 tệp)' },
                  ]}
                  value={outputFormat}
                  onChange={(e) => setOutputFormat(e.target.value)}
                  hint="Khuyên dùng WAV + MP3 để vừa lưu trữ master vừa phát trực tiếp tiện lợi."
                />

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '16px' }}>
                  <div style={{ padding: '12px', background: 'var(--neutral-50)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-default)' }}>
                    <span style={{ fontSize: '11px', color: 'var(--neutral-500)', textTransform: 'uppercase' }}>Sample Rate</span>
                    <p style={{ fontSize: '15px', fontWeight: 600, color: 'var(--neutral-900)', marginTop: '2px' }}>
                      24,000 Hz (24 kHz)
                    </p>
                    <span style={{ fontSize: '11px', color: 'var(--neutral-500)' }}>Chuẩn studio tự nhiên cho giọng nói</span>
                  </div>

                  <div style={{ padding: '12px', background: 'var(--neutral-50)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-default)' }}>
                    <span style={{ fontSize: '11px', color: 'var(--neutral-500)', textTransform: 'uppercase' }}>Channels (Kênh âm thanh)</span>
                    <p style={{ fontSize: '15px', fontWeight: 600, color: 'var(--neutral-900)', marginTop: '2px' }}>
                      Mono (1 Kênh)
                    </p>
                    <span style={{ fontSize: '11px', color: 'var(--neutral-500)' }}>Chuẩn tối ưu cho text-to-speech</span>
                  </div>
                </div>

                <Select
                  label="Thời gian nghỉ ngắt câu (Pause Policy)"
                  options={[
                    { value: '250', label: '250 ms (Nhịp điệu nhanh)' },
                    { value: '400', label: '400 ms (Tự nhiên - Khuyên dùng)' },
                    { value: '600', label: '600 ms (Chậm rãi, truyền cảm)' },
                  ]}
                  value={pausePolicy}
                  onChange={(e) => setPausePolicy(e.target.value)}
                  hint="Thời lượng ngắt quãng âm thanh chèn giữa các dấu chấm câu và phân đoạn."
                />

                <div className="ds-toggle-row">
                  <div>
                    <strong style={{ fontSize: '13px', color: 'var(--neutral-800)', display: 'block' }}>
                      Tự động cắt khoảng lặng (Silence Trim)
                    </strong>
                    <span style={{ fontSize: '12px', color: 'var(--neutral-500)' }}>
                      Loại bỏ các khoảng yên lặng thừa ở đầu và cuối tệp âm thanh kết xuất.
                    </span>
                  </div>
                  <label className="ds-switch">
                    <input
                      type="checkbox"
                      checked={silenceTrim}
                      onChange={(e) => setSilenceTrim(e.target.checked)}
                    />
                    <span className="ds-switch-slider" />
                  </label>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <Input
                    label="Thư mục lưu âm thanh xuất bản (Output Directory)"
                    value={outputDir}
                    onChange={(e) => setOutputDir(e.target.value)}
                    hint="Đường dẫn ổ đĩa lưu trữ các file WAV và MP3 tạo ra."
                  />
                  <div style={{ display: 'flex', gap: '8px' }}>
                    <Button size="sm" variant="outline" onClick={() => alert('Mở hộp thoại chọn thư mục Windows Explorer...')}>
                      Duyệt thư mục...
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => setOutputDir('D:\\Tool Dich Cho Khach\\output\\audio')}>
                      Đặt lại mặc định
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {/* ================================================================
              TAB: PERFORMANCE
              ================================================================ */}
          {activeTab === 'performance' && (
            <Card>
              <CardHeader>
                <CardTitle>Hiệu năng & Phần cứng (Performance)</CardTitle>
                <CardDescription>Cấu hình card đồ họa RTX 4050 và chính sách thử lại khi lỗi</CardDescription>
              </CardHeader>

              <CardContent style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <label className="ds-label">Bộ xử lý gia tốc (Compute Device)</label>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '12px' }}>
                    <button
                      type="button"
                      onClick={() => setDevice('gpu')}
                      style={{
                        padding: '12px 16px',
                        border: `2px solid ${device === 'gpu' ? 'var(--color-primary-600)' : 'var(--border-default)'}`,
                        backgroundColor: device === 'gpu' ? 'var(--color-primary-50)' : 'var(--surface-white)',
                        borderRadius: 'var(--radius-md)',
                        cursor: 'pointer',
                        textAlign: 'left',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '4px',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                        <strong style={{ fontSize: '14px', color: 'var(--neutral-900)' }}>GPU CUDA (Khuyên dùng)</strong>
                        <StatusBadge status="success" label="Active" size="sm" />
                      </div>
                      <span style={{ fontSize: '12px', color: 'var(--neutral-600)' }}>
                        Detected: NVIDIA GeForce RTX 4050 (6GB VRAM)
                      </span>
                    </button>

                    <button
                      type="button"
                      onClick={() => setDevice('cpu')}
                      style={{
                        padding: '12px 16px',
                        border: `2px solid ${device === 'cpu' ? 'var(--color-primary-600)' : 'var(--border-default)'}`,
                        backgroundColor: device === 'cpu' ? 'var(--color-primary-50)' : 'var(--surface-white)',
                        borderRadius: 'var(--radius-md)',
                        cursor: 'pointer',
                        textAlign: 'left',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '4px',
                      }}
                    >
                      <strong style={{ fontSize: '14px', color: 'var(--neutral-900)' }}>CPU Inference</strong>
                      <span style={{ fontSize: '12px', color: 'var(--neutral-500)' }}>
                        Chạy trên vi xử lý đa luồng (Tốc độ chậm hơn ~4-6x)
                      </span>
                    </button>
                  </div>
                </div>

                <Select
                  label="Preset chất lượng tổng hợp (Quality Preset)"
                  options={[
                    { value: 'fast', label: 'Fast (Tốc độ cao - Tiết kiệm VRAM)' },
                    { value: 'balanced', label: 'Balanced (Cân bằng chuẩn tự nhiên - Khuyên dùng)' },
                    { value: 'high', label: 'High Quality (Chất lượng âm thanh phòng thu)' },
                  ]}
                  value={qualityPreset}
                  onChange={(e) => setQualityPreset(e.target.value)}
                  hint="Điều chỉnh thuật toán nén âm thanh và độ chi tiết ngữ điệu."
                />

                <Select
                  label="Số lần thử lại khi lỗi chunk (Retry Count)"
                  options={[
                    { value: '1', label: '1 lần' },
                    { value: '2', label: '2 lần (Mặc định khuyến nghị)' },
                    { value: '3', label: '3 lần' },
                  ]}
                  value={retryCount}
                  onChange={(e) => setRetryCount(e.target.value)}
                  hint="Tự động thử lại phân đoạn khi gặp sự cố cấp phát bộ nhớ đệm trước khi báo lỗi."
                />

                <div style={{ padding: '12px', background: 'var(--neutral-50)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-default)', fontSize: '12px', color: 'var(--neutral-600)' }}>
                  <span>
                    <strong>Lưu ý:</strong> Các tham số nâng cao nội bộ của thuật toán (như <code>num_step</code>) được ẩn mặc định để bảo đảm an toàn hệ thống. Có thể cấu hình trong tab Nâng cao.
                  </span>
                </div>
              </CardContent>
            </Card>
          )}

          {/* ================================================================
              TAB: STORAGE
              ================================================================ */}
          {activeTab === 'storage' && (
            <Card>
              <CardHeader>
                <CardTitle>Cơ sở dữ liệu & Lưu trữ (Storage)</CardTitle>
                <CardDescription>Quản lý tệp SQLite, thư mục tải mô hình và bộ nhớ đệm tạm thời</CardDescription>
              </CardHeader>

              <CardContent style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                <Input
                  label="Đường dẫn tệp cơ sở dữ liệu (SQLite Database Path)"
                  value={dbPath}
                  onChange={(e) => setDbPath(e.target.value)}
                  hint="Nơi lưu trữ metadata dự án, lịch sử và snapshot trạng thái chunk."
                />

                <Input
                  label="Thư mục mô hình cục bộ (Model Checkpoints)"
                  defaultValue="D:\Tool Dich Cho Khach\models"
                  disabled
                  hint="Thư mục chứa các tệp trọng số ONNX / checkpoint offline."
                />

                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 16px', background: 'var(--neutral-50)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-default)' }}>
                  <div>
                    <strong style={{ fontSize: '13px', color: 'var(--neutral-900)' }}>Bộ nhớ đệm âm thanh tạm thời</strong>
                    <span style={{ display: 'block', fontSize: '12px', color: 'var(--neutral-500)', marginTop: '2px' }}>
                      Dung lượng hiện tại: <strong>{cacheSize}</strong>
                    </span>
                  </div>
                  <Button
                    size="sm"
                    variant="outline"
                    isLoading={isClearingCache}
                    onClick={handleClearCache}
                  >
                    Xóa Cache
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}

          {/* ================================================================
              TAB: ADVANCED
              ================================================================ */}
          {activeTab === 'advanced' && (
            <Card>
              <CardHeader>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <CardTitle>Nâng cao cho nhà phát triển (Advanced)</CardTitle>
                  <StatusBadge status="warning" label="Developer Section" size="sm" />
                </div>
                <CardDescription>
                  Cấu hình chuyên sâu thuật toán suy luận và nhật ký gỡ lỗi
                </CardDescription>
              </CardHeader>

              <CardContent style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <div className="ds-toggle-row">
                  <div>
                    <strong style={{ fontSize: '13px', color: 'var(--neutral-800)', display: 'block' }}>
                      Chế độ Nhà phát triển (Developer Mode)
                    </strong>
                    <span style={{ fontSize: '12px', color: 'var(--neutral-500)' }}>
                      Mặc định TẮT (OFF). Khi BẬT, cho phép xem tiến độ chunk, số lần thử lại (retries), mã lỗi (error codes), chẩn đoán OmniVoice, thông tin model, RTF và logs.
                    </span>
                  </div>
                  <label className="ds-switch">
                    <input
                      type="checkbox"
                      checked={isDevMode}
                      onChange={(e) => setDevMode(e.target.checked)}
                    />
                    <span className="ds-switch-slider" />
                  </label>
                </div>

                {/* Collapsed Developer Section */}
                {isDevMode ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', padding: '16px', background: 'var(--neutral-50)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-default)' }}>
                    <Select
                      label="Số bước khử nhiễu (num_step parameter)"
                      options={[
                        { value: '8', label: '8 steps (Siêu nhanh, độ chi tiết thấp)' },
                        { value: '16', label: '16 steps (Chuẩn đề xuất)' },
                        { value: '32', label: '32 steps (Chất lượng cao nhất, tốn GPU)' },
                      ]}
                      value={numSteps}
                      onChange={(e) => setNumSteps(e.target.value)}
                      hint="Giá trị num_step được áp dụng cho pipeline sinh âm thanh cục bộ."
                    />

                    <div className="ds-toggle-row">
                      <div>
                        <strong style={{ fontSize: '13px', color: 'var(--neutral-800)', display: 'block' }}>
                          SQLite WAL Mode (Write-Ahead Logging)
                        </strong>
                        <span style={{ fontSize: '12px', color: 'var(--neutral-500)' }}>
                          Cải thiện tốc độ ghi đồng thời khi xử lý song song nhiều chunk.
                        </span>
                      </div>
                      <label className="ds-switch">
                        <input
                          type="checkbox"
                          checked={sqliteWal}
                          onChange={(e) => setSqliteWal(e.target.checked)}
                        />
                        <span className="ds-switch-slider" />
                      </label>
                    </div>

                    <div className="ds-toggle-row">
                      <div>
                        <strong style={{ fontSize: '13px', color: 'var(--neutral-800)', display: 'block' }}>
                          Detailed Debug Logging
                        </strong>
                        <span style={{ fontSize: '12px', color: 'var(--neutral-500)' }}>
                          Ghi nhận chi tiết thời gian suy luận từng layer vào file nhật ký.
                        </span>
                      </div>
                      <label className="ds-switch">
                        <input
                          type="checkbox"
                          checked={debugLogs}
                          onChange={(e) => setDebugLogs(e.target.checked)}
                        />
                        <span className="ds-switch-slider" />
                      </label>
                    </div>
                  </div>
                ) : (
                  <div style={{ padding: '16px', textAlign: 'center', background: 'var(--neutral-50)', borderRadius: 'var(--radius-md)', border: '1px dashed var(--border-strong)', color: 'var(--neutral-500)', fontSize: '13px' }}>
                    Phần cài đặt dành cho nhà phát triển đang được thu gọn. Hãy bật công tắc phía trên để mở khóa các tham số kỹ thuật.
                  </div>
                )}
              </CardContent>

              <CardFooter style={{ justifyContent: 'flex-end' }}>
                <Button variant="primary" size="md" onClick={handleSaveSettings}>
                  Lưu cấu hình nâng cao
                </Button>
              </CardFooter>
            </Card>
          )}

        </div>
      </div>
    </div>
  );
};
