import React, { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Button,
  StatusBadge,
  SearchInput,
  ConfirmDialog,
  Modal,
  ErrorState,
  EmptyState,
} from '../components';
import { useVoiceProfiles } from '../hooks';
import { voiceProfileService, type VoiceProfile, type ReferenceAudioInfo } from '../services/voiceProfileService';
import { ApiError, NetworkError } from '../services/httpClient';

function describeError(err: unknown): string {
  if (err instanceof ApiError) return `${err.message} (${err.code})`;
  if (err instanceof NetworkError) return err.message;
  if (err instanceof Error) return err.message;
  return 'Đã xảy ra lỗi không xác định.';
}

function formatReference(reference?: ReferenceAudioInfo | null): string {
  if (!reference) return 'Chưa có dữ liệu mẫu tham chiếu';
  const duration = `${reference.duration_seconds.toFixed(1)}s`;
  return `${duration} • ${reference.sample_rate.toLocaleString('vi-VN')}Hz • ${reference.channels}ch`;
}

export const VoicesPage: React.FC = () => {
  const navigate = useNavigate();
  const { profiles, loading, error, reload } = useVoiceProfiles();

  const [searchQuery, setSearchQuery] = useState('');

  // Details modal
  const [detailsProfile, setDetailsProfile] = useState<VoiceProfile | null>(null);

  // Delete flow
  const [deleteTarget, setDeleteTarget] = useState<VoiceProfile | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const filteredProfiles = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return profiles;
    return profiles.filter(
      (p) => p.name.toLowerCase().includes(q) || p.provider.toLowerCase().includes(q)
    );
  }, [profiles, searchQuery]);

  const handleUseProfile = (_profile: VoiceProfile) => {
    navigate('/clone');
  };

  const handleConfirmDelete = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      await voiceProfileService.remove(deleteTarget.profile_id);
      setDeleteTarget(null);
      void reload();
    } catch (err) {
      setDeleteError(describeError(err));
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Top Header & Add Voice Button */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h1 style={{ fontSize: '20px', fontWeight: 700, color: 'var(--neutral-900)' }}>
            Voice Library (Thư viện giọng nói)
          </h1>
          <p style={{ fontSize: '13px', color: 'var(--neutral-500)', marginTop: '2px' }}>
            {loading ? 'Đang tải danh sách giọng đã nhân bản...' : `Quản lý ${profiles.length} giọng đã nhân bản (Voice Cloning)`}
          </p>
        </div>

        <Button
          variant="primary"
          size="md"
          onClick={() => navigate('/clone')}
          iconLeft={
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="12" y1="5" x2="12" y2="19"></line>
              <line x1="5" y1="12" x2="19" y2="12"></line>
            </svg>
          }
        >
          Add Voice (Nhân bản mới)
        </Button>
      </div>

      {/* Load error */}
      {error && (
        <ErrorState
          title="Không tải được danh sách giọng"
          message={error.message}
          details={error.code}
          retryLabel="Thử lại"
          onRetry={() => void reload()}
        />
      )}

      {/* Delete error (kept visible until the user retries or dismisses via a new attempt) */}
      {deleteError && (
        <ErrorState
          title="Không thể xóa Voice Profile"
          message={deleteError}
          retryLabel="Đóng"
          onRetry={() => setDeleteError(null)}
        />
      )}

      {/* Search Bar */}
      {!loading && profiles.length > 0 && (
        <SearchInput
          value={searchQuery}
          onChange={setSearchQuery}
          placeholder="Tìm theo tên giọng hoặc provider..."
        />
      )}

      {/* Empty state: no profiles at all yet */}
      {!loading && !error && profiles.length === 0 && (
        <EmptyState
          title="Chưa có Voice Profile nào"
          description="Nhân bản giọng nói đầu tiên của bạn để bắt đầu sử dụng Voice Cloning."
          actionLabel="Nhân bản giọng mới"
          onAction={() => navigate('/clone')}
        />
      )}

      {/* No results for current search */}
      {!loading && profiles.length > 0 && filteredProfiles.length === 0 && (
        <div style={{ padding: '48px 16px', textAlign: 'center', background: 'var(--surface-white)', borderRadius: 'var(--radius-lg)', border: '1px dashed var(--border-strong)' }}>
          <h3 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--neutral-800)' }}>
            Không tìm thấy giọng nói phù hợp
          </h3>
          <p style={{ fontSize: '13px', color: 'var(--neutral-500)', marginTop: '4px' }}>
            Thử thay đổi từ khóa tìm kiếm khác.
          </p>
        </div>
      )}

      {/* Voice Cards Grid */}
      {filteredProfiles.length > 0 && (
        <div className="ds-voices-grid">
          {filteredProfiles.map((item) => (
            <div key={item.profile_id} className="ds-voice-card">
              {/* Card Header */}
              <div className="ds-voice-card-header">
                <div>
                  <h3 className="ds-voice-card-title">{item.name}</h3>
                  <div style={{ display: 'flex', gap: '6px', alignItems: 'center', marginTop: '4px' }}>
                    <StatusBadge status="success" label="Sẵn sàng" size="sm" />
                    <span style={{ fontSize: '11px', color: 'var(--neutral-500)' }}>{item.provider}</span>
                  </div>
                </div>
              </div>

              {/* Card Body */}
              <div className="ds-voice-card-body">
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', paddingTop: '4px' }}>
                  <div className="ds-voice-card-stat">
                    <span>Mẫu tham chiếu:</span>
                    <strong style={{ color: 'var(--neutral-800)' }}>{formatReference(item.reference)}</strong>
                  </div>
                </div>
              </div>

              {/* Card Footer Actions */}
              <div className="ds-voice-card-footer">
                <div style={{ display: 'flex', gap: '6px' }}>
                  <Button size="sm" variant="primary" onClick={() => handleUseProfile(item)}>
                    Dùng để thử giọng
                  </Button>
                </div>

                <div style={{ display: 'flex', gap: '4px' }}>
                  <Button
                    size="sm"
                    variant="ghost"
                    title="Chi tiết"
                    onClick={() => setDetailsProfile(item)}
                  >
                    Chi tiết
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    style={{ color: 'var(--danger-text)' }}
                    title="Xóa giọng"
                    onClick={() => {
                      setDeleteError(null);
                      setDeleteTarget(item);
                    }}
                  >
                    Xóa
                  </Button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ==================================================================
          MODALS: DETAILS, CONFIRM DELETE
          ================================================================== */}

      {/* Voice Details Modal */}
      <Modal
        isOpen={Boolean(detailsProfile)}
        onClose={() => setDetailsProfile(null)}
        title="Thông tin chi tiết Voice Profile"
        size="md"
        footer={
          <Button variant="primary" size="md" onClick={() => setDetailsProfile(null)}>
            Xong
          </Button>
        }
      >
        {detailsProfile && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', fontSize: '13px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--border-subtle)' }}>
              <span style={{ color: 'var(--neutral-500)' }}>Tên giọng:</span>
              <strong>{detailsProfile.name}</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--border-subtle)' }}>
              <span style={{ color: 'var(--neutral-500)' }}>Provider:</span>
              <strong>{detailsProfile.provider}</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--border-subtle)' }}>
              <span style={{ color: 'var(--neutral-500)' }}>Trạng thái:</span>
              <StatusBadge status="success" label="Sẵn sàng" size="sm" />
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--border-subtle)' }}>
              <span style={{ color: 'var(--neutral-500)' }}>Mẫu tham chiếu:</span>
              <strong>{formatReference(detailsProfile.reference)}</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0' }}>
              <span style={{ color: 'var(--neutral-500)' }}>Profile ID:</span>
              <code style={{ fontSize: '11px' }}>{detailsProfile.profile_id}</code>
            </div>
          </div>
        )}
      </Modal>

      {/* Delete Confirmation Dialog */}
      <ConfirmDialog
        isOpen={Boolean(deleteTarget)}
        onClose={() => setDeleteTarget(null)}
        onConfirm={handleConfirmDelete}
        title="Xóa Voice Profile"
        message={`Bạn có chắc chắn muốn xóa "${deleteTarget?.name || ''}" khỏi Voice Library? Hành động này không thể hoàn tác. Nếu hồ sơ này đang được một tác vụ Long-form sử dụng, thao tác xóa sẽ bị từ chối.`}
        confirmLabel="Xóa vĩnh viễn"
        isDestructive
        isLoading={deleting}
      />
    </div>
  );
};
