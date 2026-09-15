import React, { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  Button,
  StatusBadge,
  ProgressBar,
  AudioPlayer,
} from '../components';
import { useDeveloperMode } from '../hooks';

interface ProjectChunk {
  index: number;
  textPreview: string;
  duration: string;
  status: 'COMPLETED' | 'GENERATING' | 'PENDING' | 'FAILED';
  attempts: string;
}

const SAMPLE_CHUNKS: ProjectChunk[] = [
  {
    index: 1,
    textPreview: 'Mặt trời bắt đầu nhô lên khỏi rặng núi phía đông, rải những tia nắng ấm áp đầu tiên...',
    duration: '14.2s',
    status: 'COMPLETED',
    attempts: '1/3',
  },
  {
    index: 2,
    textPreview: 'Những giọt sương mai đọng trên ngọn cỏ lấp lánh như hàng vạn viên ngọc bích tuyệt mỹ...',
    duration: '12.8s',
    status: 'COMPLETED',
    attempts: '1/3',
  },
  {
    index: 3,
    textPreview: 'Gió sớm khẽ lay động cành lá non, mang theo hương thơm ngai ngái của đất trời vừa thức giấc...',
    duration: '15.1s',
    status: 'COMPLETED',
    attempts: '1/3',
  },
  {
    index: 4,
    textPreview: 'Từ xa xa, tiếng chim sơn ca ríu rít cất lên bài ca đón chào ngày mới trong trẻo...',
    duration: '13.4s',
    status: 'COMPLETED',
    attempts: '1/3',
  },
  {
    index: 67,
    textPreview: 'Đàn ngựa của bộ tộc bắt đầu gặm cỏ quanh bờ suối trong vắt, nơi làn nước phản chiếu sắc trời...',
    duration: '14.0s',
    status: 'COMPLETED',
    attempts: '1/3',
  },
  {
    index: 68,
    textPreview: 'Một cảm giác thanh bình kỳ lạ bao trùm khắp không gian, khiến bất kỳ ai đặt chân đến đây...',
    duration: '--',
    status: 'FAILED',
    attempts: '2/3',
  },
  {
    index: 69,
    textPreview: 'Người lữ khách dừng chân bên gốc cây cổ thụ ngàn năm, khẽ mỉm cười và hít thở thật sâu...',
    duration: '--',
    status: 'PENDING',
    attempts: '0/3',
  },
  {
    index: 70,
    textPreview: 'Hành trình dài vượt qua dãy núi tuyết hiểm trở cuối cùng cũng đã đưa anh tới vùng đất hứa...',
    duration: '--',
    status: 'PENDING',
    attempts: '0/3',
  },
];

export const ProjectDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const { isDevMode } = useDeveloperMode();

  const [projectStatus, setProjectStatus] = useState<'IN_PROGRESS' | 'PAUSED' | 'COMPLETED'>('COMPLETED');
  const [chunks, setChunks] = useState<ProjectChunk[]>(SAMPLE_CHUNKS);
  const [currentlyPlayingIndex, setCurrentlyPlayingIndex] = useState<number | null>(null);

  const completedCount = chunks.filter((c) => c.status === 'COMPLETED').length;
  const progressPercent = projectStatus === 'COMPLETED' ? 100 : Math.round((completedCount / chunks.length) * 100);

  const handlePlayChunk = (idx: number) => {
    if (currentlyPlayingIndex === idx) {
      setCurrentlyPlayingIndex(null);
    } else {
      setCurrentlyPlayingIndex(idx);
    }
  };

  const handleRetryChunk = (idx: number) => {
    setChunks((prev) =>
      prev.map((c) =>
        c.index === idx
          ? { ...c, status: 'COMPLETED', duration: '13.8s', attempts: '2/3' }
          : c
      )
    );
  };

  const handleRetryAllFailed = () => {
    setChunks((prev) =>
      prev.map((c) =>
        c.status === 'FAILED'
          ? { ...c, status: 'COMPLETED', duration: '13.8s', attempts: '2/3' }
          : c
      )
    );
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Developer Mode Active Banner */}
      {isDevMode && (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 14px', background: 'var(--neutral-100)', border: '1px dashed var(--neutral-400)', borderRadius: 'var(--radius-md)', fontSize: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <StatusBadge status="warning" label="Developer Mode ON" size="sm" />
            <span style={{ color: 'var(--neutral-700)' }}>
              Developer diagnostics & debug controls unlocked for this project.
            </span>
          </div>
          <span style={{ color: 'var(--neutral-500)', fontFamily: 'var(--font-family-mono)' }}>
            Total Chunks: {chunks.length} • Failed: {chunks.filter(c => c.status === 'FAILED').length}
          </span>
        </div>
      )}

      {/* Top breadcrumb & back link */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <Link
          to="/long-form"
          style={{ fontSize: '13px', color: 'var(--color-primary-600)', display: 'flex', alignItems: 'center', gap: '4px', fontWeight: 500 }}
        >
          ← Quay lại Long-form Studio
        </Link>
        <span style={{ fontSize: '12px', color: 'var(--neutral-500)' }}>
          Mã dự án: <code>{id || 'proj-longform-01'}</code>
        </span>
      </div>

      {/* Project Meta Card */}
      <Card>
        <CardHeader>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <CardTitle>Chương 1: Bình minh trên thảo nguyên</CardTitle>
                <StatusBadge
                  status={
                    projectStatus === 'COMPLETED'
                      ? 'success'
                      : projectStatus === 'PAUSED'
                      ? 'warning'
                      : 'info'
                  }
                  label={
                    projectStatus === 'COMPLETED'
                      ? 'Hoàn tất'
                      : projectStatus === 'PAUSED'
                      ? 'Tạm dừng'
                      : 'Đang xử lý'
                  }
                />
              </div>
              <CardDescription style={{ marginTop: '4px' }}>
                Giọng đọc: <strong>Hoài My (Nữ Miền Bắc)</strong> • Ngôn ngữ: <strong>Tiếng Việt</strong> • Thời lượng: <strong>18 phút 42 giây</strong>
                {isDevMode && <span> • <em>SQLite Chunks Persistent</em></span>}
              </CardDescription>
            </div>

            {/* Customer vs Developer Action Controls */}
            {isDevMode ? (
              /* Developer Debug Controls */
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => alert('Phát toàn bộ danh sách các đoạn đã tạo...')}
                  iconLeft={
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                      <polygon points="5 3 19 12 5 21 5 3"></polygon>
                    </svg>
                  }
                >
                  Play All
                </Button>

                {projectStatus === 'PAUSED' ? (
                  <Button
                    size="sm"
                    variant="primary"
                    onClick={() => setProjectStatus('IN_PROGRESS')}
                  >
                    Resume
                  </Button>
                ) : (
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => setProjectStatus('PAUSED')}
                  >
                    Pause
                  </Button>
                )}

                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => alert('Đang kích hoạt quy trình tái tổng hợp toàn bộ...')}
                >
                  Retry
                </Button>

                <Button
                  size="sm"
                  variant="danger"
                  onClick={handleRetryAllFailed}
                >
                  Retry Failed
                </Button>
              </div>
            ) : (
              /* Friendly Customer Actions */
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                {projectStatus !== 'COMPLETED' && (
                  projectStatus === 'PAUSED' ? (
                    <Button
                      size="sm"
                      variant="primary"
                      onClick={() => setProjectStatus('IN_PROGRESS')}
                    >
                      Tiếp tục tạo
                    </Button>
                  ) : (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setProjectStatus('PAUSED')}
                    >
                      Tạm dừng
                    </Button>
                  )
                )}

                <Button
                  size="sm"
                  variant="outline"
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
                  size="sm"
                  variant="outline"
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
              </div>
            )}
          </div>
        </CardHeader>

        <CardContent style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px' }}>
            <span style={{ color: 'var(--neutral-600)' }}>
              {isDevMode
                ? `Tiến độ phân đoạn tổng thể (${completedCount} / ${chunks.length} chunks)`
                : 'Tiến độ xử lý audio'
              }
            </span>
            <span style={{ fontWeight: 600, color: 'var(--neutral-900)' }}>{progressPercent}%</span>
          </div>
          <ProgressBar value={progressPercent} size="md" status="default" />
        </CardContent>
      </Card>

      {/* Customer Audio Player */}
      <Card>
        <CardHeader>
          <CardTitle>Bản nghe âm thanh hoàn chỉnh</CardTitle>
          <CardDescription>
            Nghe trực tiếp toàn bộ dự án âm thanh hoặc tua đến vị trí mong muốn
          </CardDescription>
        </CardHeader>
        <CardContent>
          <AudioPlayer
            title="Chương 1: Bình minh trên thảo nguyên"
            duration={1122}
            voice="Hoài My (Nữ Miền Bắc)"
            language="Tiếng Việt"
            onDownloadWav={() => alert('Đang tải xuống tệp WAV...')}
            onDownloadMp3={() => alert('Đang tải xuống tệp MP3...')}
          />
        </CardContent>
      </Card>

      {/* Customer Project Text Preview */}
      <Card>
        <CardHeader>
          <CardTitle>Nội dung văn bản</CardTitle>
          <CardDescription>
            Văn bản gốc được sử dụng để chuyển đổi thành giọng nói
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div
            style={{
              padding: '16px',
              background: 'var(--neutral-50)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-subtle)',
              fontSize: '14px',
              lineHeight: '1.7',
              color: 'var(--neutral-800)',
              maxHeight: '260px',
              overflowY: 'auto',
              whiteSpace: 'pre-wrap',
            }}
          >
            {`Mặt trời bắt đầu nhô lên khỏi rặng núi phía đông, rải những tia nắng ấm áp đầu tiên xuống thảo nguyên bao la bát ngát. Những giọt sương mai đọng trên ngọn cỏ lấp lánh như hàng vạn viên ngọc bích tuyệt mỹ. Gió sớm khẽ lay động cành lá non, mang theo hương thơm ngai ngái của đất trời vừa thức giấc sau một đêm dài yên bình.\n\nTừ xa xa, tiếng chim sơn ca ríu rít cất lên bài ca đón chào ngày mới. Đàn ngựa của bộ tộc bắt đầu gặm cỏ quanh bờ suối trong vắt, nơi làn nước trong veo phản chiếu sắc trời xanh ngắt. Một cảm giác thanh bình kỳ lạ bao trùm khắp không gian, khiến bất kỳ ai đặt chân đến đây cũng cảm nhận được sự tự do và khoáng đạt vô tận của thiên nhiên.\n\nNgười lữ khách dừng chân bên gốc cây cổ thụ ngàn năm, khẽ mỉm cười và hít thở thật sâu luồng không khí thanh sạch. Hành trình dài vượt qua dãy núi tuyết hiểm trở cuối cùng cũng đã đưa anh tới vùng đất hứa - nơi khởi đầu của những truyền thuyết huyền thoại ngàn năm về trước.`}
          </div>
        </CardContent>
      </Card>

      {/* Developer Chunks Inspector Table (ONLY rendered when Developer Mode is enabled) */}
      {isDevMode && (
        <Card>
          <CardHeader>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <CardTitle>Bảng chi tiết phân đoạn (Developer Chunk Table)</CardTitle>
                <CardDescription>
                  Theo dõi từng đoạn văn bản, thời lượng, số lần thử và phát âm thanh kiểm tra (Chỉ hiển thị khi bật Developer Mode)
                </CardDescription>
              </div>
              <span style={{ fontSize: '12px', color: 'var(--neutral-500)' }}>
                {chunks.length} phân đoạn hiển thị
              </span>
            </div>
          </CardHeader>

          <CardContent style={{ padding: 0 }}>
            <div className="ds-table-wrapper" style={{ border: 'none', borderRadius: 0, boxShadow: 'none' }}>
              <table className="ds-table">
                <thead>
                  <tr>
                    <th className="ds-th" style={{ width: '80px' }}>Index</th>
                    <th className="ds-th">Text Preview</th>
                    <th className="ds-th" style={{ width: '100px' }}>Duration</th>
                    <th className="ds-th" style={{ width: '130px' }}>Status</th>
                    <th className="ds-th" style={{ width: '90px' }}>Attempts</th>
                    <th className="ds-th" style={{ width: '120px', textAlign: 'right' }}>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {chunks.map((chunk) => {
                    const isPlaying = currentlyPlayingIndex === chunk.index;
                    return (
                      <tr key={chunk.index} className="ds-tr">
                        <td className="ds-td">
                          <span style={{ fontFamily: 'var(--font-family-mono)', fontWeight: 600 }}>
                            #{chunk.index}
                          </span>
                        </td>
                        <td className="ds-td">
                          <span style={{ fontSize: '13px', color: 'var(--neutral-800)', lineHeight: '1.5' }}>
                            {chunk.textPreview}
                          </span>
                        </td>
                        <td className="ds-td">
                          <span style={{ fontFamily: 'var(--font-family-mono)', fontSize: '12px', color: 'var(--neutral-600)' }}>
                            {chunk.duration}
                          </span>
                        </td>
                        <td className="ds-td">
                          <StatusBadge
                            size="sm"
                            status={
                              chunk.status === 'COMPLETED'
                                ? 'success'
                                : chunk.status === 'FAILED'
                                ? 'error'
                                : chunk.status === 'GENERATING'
                                ? 'info'
                                : 'neutral'
                            }
                            label={chunk.status}
                          />
                        </td>
                        <td className="ds-td">
                          <span style={{ fontSize: '12px', color: 'var(--neutral-600)', fontFamily: 'var(--font-family-mono)' }}>
                            {chunk.attempts}
                          </span>
                        </td>
                        <td className="ds-td" style={{ textAlign: 'right' }}>
                          {chunk.status === 'COMPLETED' ? (
                            <Button
                              size="sm"
                              variant={isPlaying ? 'primary' : 'outline'}
                              onClick={() => handlePlayChunk(chunk.index)}
                              iconLeft={
                                isPlaying ? (
                                  <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
                                    <rect x="6" y="4" width="4" height="16"></rect>
                                    <rect x="14" y="4" width="4" height="16"></rect>
                                  </svg>
                                ) : (
                                  <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
                                    <polygon points="5 3 19 12 5 21 5 3"></polygon>
                                  </svg>
                                )
                              }
                            >
                              {isPlaying ? 'Pause' : 'Play'}
                            </Button>
                          ) : chunk.status === 'FAILED' ? (
                            <Button
                              size="sm"
                              variant="danger"
                              onClick={() => handleRetryChunk(chunk.index)}
                            >
                              Retry
                            </Button>
                          ) : (
                            <span style={{ fontSize: '12px', color: 'var(--neutral-400)' }}>Chờ...</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
};
