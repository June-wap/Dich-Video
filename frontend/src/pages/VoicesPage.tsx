import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Button,
  StatusBadge,
  SearchInput,
  FilterBar,
  ConfirmDialog,
  Modal,
  Input,
  AudioPlayer,
} from '../components';
import { voiceService, type VoiceItem } from '../services';

export type VoiceStatus = 'Verified' | 'Needs Review' | 'Unavailable';
export type VoiceType = 'Built-in' | 'Cloned' | 'Community';

export const VoicesPage: React.FC = () => {
  const navigate = useNavigate();

  const [voices, setVoices] = useState<VoiceItem[]>([]);

  useEffect(() => {
    voiceService.getVoices().then(setVoices);
  }, []);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedLangFilter, setSelectedLangFilter] = useState('ALL');

  // Modals state
  const [previewVoice, setPreviewVoice] = useState<VoiceItem | null>(null);
  const [detailsVoice, setDetailsVoice] = useState<VoiceItem | null>(null);
  const [renameVoice, setRenameVoice] = useState<VoiceItem | null>(null);
  const [newName, setNewName] = useState('');
  const [deleteTargetVoice, setDeleteTargetVoice] = useState<VoiceItem | null>(null);

  // Filter options with counts
  const filterOptions = useMemo(() => {
    return [
      { id: 'ALL', label: 'Tất cả', count: voices.length },
      { id: 'vi', label: 'Vietnamese', count: voices.filter((v) => v.languageCode === 'vi').length },
      { id: 'en', label: 'English', count: voices.filter((v) => v.languageCode === 'en').length },
      { id: 'zh', label: 'Chinese', count: voices.filter((v) => v.languageCode === 'zh').length },
      { id: 'ja', label: 'Japanese', count: voices.filter((v) => v.languageCode === 'ja').length },
      { id: 'fr', label: 'French', count: voices.filter((v) => v.languageCode === 'fr').length },
      { id: 'es', label: 'Spanish', count: voices.filter((v) => v.languageCode === 'es').length },
    ];
  }, [voices]);

  // Filtered voice items
  const filteredVoices = useMemo(() => {
    return voices.filter((v) => {
      const matchesSearch =
        searchQuery.trim() === '' ||
        v.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        v.language.toLowerCase().includes(searchQuery.toLowerCase()) ||
        v.type.toLowerCase().includes(searchQuery.toLowerCase());

      const matchesLang =
        selectedLangFilter === 'ALL' || v.languageCode === selectedLangFilter;

      return matchesSearch && matchesLang;
    });
  }, [voices, searchQuery, selectedLangFilter]);

  // Actions
  const handleUseVoice = (_voice: VoiceItem) => {
    navigate('/tts');
  };

  const handleConfirmRename = () => {
    if (!renameVoice || !newName.trim()) return;
    setVoices((prev) =>
      prev.map((v) => (v.id === renameVoice.id ? { ...v, name: newName.trim() } : v))
    );
    setRenameVoice(null);
  };

  const handleConfirmDelete = () => {
    if (!deleteTargetVoice) return;
    setVoices((prev) => prev.filter((v) => v.id !== deleteTargetVoice.id));
    setDeleteTargetVoice(null);
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
            Quản lý {voices.length} giọng đọc bản xứ, giọng nhân bản và mô hình AI cục bộ
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

      {/* Search & Language Filters Bar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
        <SearchInput
          value={searchQuery}
          onChange={setSearchQuery}
          placeholder="Tìm giọng, ngôn ngữ hoặc thể loại..."
        />

        <FilterBar
          options={filterOptions}
          activeId={selectedLangFilter}
          onSelect={setSelectedLangFilter}
        />
      </div>

      {/* Voice Cards Grid (Supports arbitrary voice count) */}
      {filteredVoices.length === 0 ? (
        <div style={{ padding: '48px 16px', textAlign: 'center', background: 'var(--surface-white)', borderRadius: 'var(--radius-lg)', border: '1px dashed var(--border-strong)' }}>
          <h3 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--neutral-800)' }}>
            Không tìm thấy giọng nói phù hợp
          </h3>
          <p style={{ fontSize: '13px', color: 'var(--neutral-500)', marginTop: '4px' }}>
            Thử thay đổi từ khóa tìm kiếm hoặc chọn bộ lọc ngôn ngữ khác.
          </p>
        </div>
      ) : (
        <div className="ds-voices-grid">
          {filteredVoices.map((item) => (
            <div key={item.id} className="ds-voice-card">
              {/* Card Header */}
              <div className="ds-voice-card-header">
                <div>
                  <h3 className="ds-voice-card-title">{item.name}</h3>
                  <div style={{ display: 'flex', gap: '6px', alignItems: 'center', marginTop: '4px' }}>
                    <StatusBadge
                      status={
                        item.status === 'Verified'
                          ? 'success'
                          : item.status === 'Needs Review'
                          ? 'warning'
                          : 'error'
                      }
                      label={item.status}
                      size="sm"
                    />
                    <span style={{ fontSize: '11px', color: 'var(--neutral-500)' }}>
                      {item.language}
                    </span>
                  </div>
                </div>

                <StatusBadge
                  status={item.type === 'Built-in' ? 'info' : item.type === 'Cloned' ? 'neutral' : 'warning'}
                  label={item.type}
                  size="sm"
                  showDot={false}
                />
              </div>

              {/* Card Body */}
              <div className="ds-voice-card-body">
                <p style={{ fontSize: '13px', color: 'var(--neutral-600)', lineHeight: '1.5', minHeight: '40px' }}>
                  {item.description}
                </p>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', borderTop: '1px solid var(--border-subtle)', paddingTop: '10px' }}>
                  <div className="ds-voice-card-stat">
                    <span>Mẫu tham chiếu:</span>
                    <strong style={{ color: 'var(--neutral-800)' }}>{item.referenceDuration}</strong>
                  </div>
                  <div className="ds-voice-card-stat">
                    <span>Dùng gần nhất:</span>
                    <span>{item.lastUsed}</span>
                  </div>
                </div>
              </div>

              {/* Card Footer Actions */}
              <div className="ds-voice-card-footer">
                <div style={{ display: 'flex', gap: '6px' }}>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => setPreviewVoice(item)}
                  >
                    Preview
                  </Button>
                  <Button
                    size="sm"
                    variant="primary"
                    disabled={item.status === 'Unavailable'}
                    onClick={() => handleUseVoice(item)}
                  >
                    Use
                  </Button>
                </div>

                {/* Overflow / secondary actions */}
                <div style={{ display: 'flex', gap: '4px' }}>
                  <Button
                    size="sm"
                    variant="ghost"
                    title="Chi tiết"
                    onClick={() => setDetailsVoice(item)}
                  >
                    Chi tiết
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    title="Đổi tên"
                    onClick={() => {
                      setRenameVoice(item);
                      setNewName(item.name);
                    }}
                  >
                    Đổi tên
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    style={{ color: 'var(--danger-text)' }}
                    title="Xóa giọng"
                    onClick={() => setDeleteTargetVoice(item)}
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
          MODALS: PREVIEW, DETAILS, RENAME, CONFIRM DELETE
          ================================================================== */}

      {/* Preview Voice Audio Player Modal */}
      <Modal
        isOpen={Boolean(previewVoice)}
        onClose={() => setPreviewVoice(null)}
        title={`Nghe thử mẫu: ${previewVoice?.name || ''}`}
        size="md"
        footer={
          <Button variant="outline" size="md" onClick={() => setPreviewVoice(null)}>
            Đóng
          </Button>
        }
      >
        {previewVoice && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <p style={{ fontSize: '13px', color: 'var(--neutral-600)' }}>
              Đoạn âm thanh mẫu trích xuất từ bộ nhớ đệm cục bộ của mô hình giọng nói.
            </p>
            <AudioPlayer
              title={`Sample Voice: ${previewVoice.name}`}
              duration={9.2}
              voice={previewVoice.name}
              language={previewVoice.language}
            />
          </div>
        )}
      </Modal>

      {/* Voice Details Modal */}
      <Modal
        isOpen={Boolean(detailsVoice)}
        onClose={() => setDetailsVoice(null)}
        title="Thông tin chi tiết Voice Profile"
        size="md"
        footer={
          <Button variant="primary" size="md" onClick={() => setDetailsVoice(null)}>
            Xong
          </Button>
        }
      >
        {detailsVoice && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', fontSize: '13px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--border-subtle)' }}>
              <span style={{ color: 'var(--neutral-500)' }}>Tên giọng:</span>
              <strong>{detailsVoice.name}</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--border-subtle)' }}>
              <span style={{ color: 'var(--neutral-500)' }}>Ngôn ngữ:</span>
              <strong>{detailsVoice.language} ({detailsVoice.languageCode})</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--border-subtle)' }}>
              <span style={{ color: 'var(--neutral-500)' }}>Phân loại:</span>
              <StatusBadge status="neutral" label={detailsVoice.type} size="sm" showDot={false} />
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--border-subtle)' }}>
              <span style={{ color: 'var(--neutral-500)' }}>Trạng thái xác thực:</span>
              <StatusBadge
                status={detailsVoice.status === 'Verified' ? 'success' : detailsVoice.status === 'Needs Review' ? 'warning' : 'error'}
                label={detailsVoice.status}
                size="sm"
              />
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--border-subtle)' }}>
              <span style={{ color: 'var(--neutral-500)' }}>Tần số lấy mẫu (Sample Rate):</span>
              <code>24,000 Hz / 16-bit PCM</code>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0' }}>
              <span style={{ color: 'var(--neutral-500)' }}>Lưu trữ dữ liệu:</span>
              <code>Local SQLite + Checkpoint dir</code>
            </div>
          </div>
        )}
      </Modal>

      {/* Rename Voice Modal */}
      <Modal
        isOpen={Boolean(renameVoice)}
        onClose={() => setRenameVoice(null)}
        title="Đổi tên Voice Profile"
        size="sm"
        footer={
          <>
            <Button variant="outline" size="md" onClick={() => setRenameVoice(null)}>
              Hủy
            </Button>
            <Button variant="primary" size="md" onClick={handleConfirmRename}>
              Lưu thay đổi
            </Button>
          </>
        }
      >
        <Input
          label="Tên hiển thị mới"
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          placeholder="Nhập tên mới..."
        />
      </Modal>

      {/* Delete Confirmation Dialog */}
      <ConfirmDialog
        isOpen={Boolean(deleteTargetVoice)}
        onClose={() => setDeleteTargetVoice(null)}
        onConfirm={handleConfirmDelete}
        title="Xóa Voice Profile"
        message={`Bạn có chắc chắn muốn xóa "${deleteTargetVoice?.name || ''}" khỏi Voice Library? Các dự án cũ đã xuất file âm thanh vẫn sẽ được giữ nguyên.`}
        confirmLabel="Xóa vĩnh viễn"
        isDestructive
      />
    </div>
  );
};
