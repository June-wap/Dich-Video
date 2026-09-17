import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, StatusBadge, SearchInput, DataTable, Modal, AudioPlayer, ErrorState } from '../components';
import type { ColumnDef } from '../components/DataTable/DataTable';
import { ttsJobService } from '../services/ttsJobService';
import type { TtsJob } from '../services/ttsJobService';
import { ApiError, NetworkError } from '../services/httpClient';

function describeError(err: unknown): string {
  if (err instanceof ApiError) return `${err.message} (${err.code})`;
  if (err instanceof NetworkError) return err.message;
  if (err instanceof Error) return err.message;
  return 'Đã xảy ra lỗi không xác định.';
}

export const HistoryPage: React.FC = () => {
  const navigate = useNavigate();

  const [history, setHistory] = useState<TtsJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');

  const loadHistory = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const items = await ttsJobService.list();
      setHistory([...items].reverse()); // backend returns oldest-first; show newest-first
    } catch (err) {
      setError(describeError(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadHistory();
  }, [loadHistory]);

  // Play modal
  const [playingJob, setPlayingJob] = useState<TtsJob | null>(null);
  const [replayError, setReplayError] = useState(false);
  useEffect(() => setReplayError(false), [playingJob?.job_id]);

  const filteredHistory = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return history;
    return history.filter((item) => item.job_id.toLowerCase().includes(q));
  }, [history, searchQuery]);

  const columns: ColumnDef<TtsJob>[] = useMemo(
    () => [
      {
        key: 'job_id',
        header: 'Job ID',
        width: '140px',
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
        key: 'status',
        header: 'Trạng thái',
        width: '130px',
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
        width: '100px',
        render: (item) => {
          const fmt = ttsJobService.guessFormat(item);
          return <span style={{ fontSize: '12px', color: 'var(--neutral-600)' }}>{fmt ? fmt.toUpperCase() : '—'}</span>;
        },
      },
      {
        key: 'actions',
        header: 'Hành động',
        width: '160px',
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

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Top Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <h1 style={{ fontSize: '20px', fontWeight: 700, color: 'var(--neutral-900)' }}>
            History (Lịch sử Text to Speech)
          </h1>
          <p style={{ fontSize: '13px', color: 'var(--neutral-500)', marginTop: '2px' }}>
            Đọc trực tiếp từ backend, còn nguyên sau khi tải lại trang. Chỉ gồm các tác vụ Text to Speech — Voice
            Cloning chưa có API liệt kê lịch sử.
          </p>
        </div>
        <Button size="sm" variant="ghost" onClick={() => void loadHistory()} disabled={loading}>
          Làm mới
        </Button>
      </div>

      {/* Load error */}
      {error && (
        <ErrorState title="Không thể tải lịch sử" message={error} retryLabel="Thử lại" onRetry={() => void loadHistory()} />
      )}

      {/* Search */}
      {!loading && !error && history.length > 0 && (
        <SearchInput value={searchQuery} onChange={setSearchQuery} placeholder="Tìm theo Job ID..." />
      )}

      {/* History DataTable */}
      {!error && (
        <DataTable
          columns={columns}
          data={loading ? [] : filteredHistory}
          keyExtractor={(item) => item.job_id}
          emptyTitle={loading ? 'Đang tải lịch sử...' : 'Chưa có lịch sử tác vụ'}
          emptyDescription={
            loading
              ? 'Vui lòng đợi trong giây lát.'
              : 'Các tác vụ Text to Speech bạn tạo sẽ xuất hiện tại đây, kể cả sau khi tải lại trang.'
          }
        />
      )}

      {!loading && !error && history.length === 0 && (
        <div style={{ display: 'flex', justifyContent: 'center' }}>
          <Button variant="primary" size="md" onClick={() => navigate('/tts')}>
            Tạo Text to Speech đầu tiên
          </Button>
        </div>
      )}

      {/* Play Audio Modal */}
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
    </div>
  );
};
