import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Button,
  StatusBadge,
  SearchInput,
  FilterBar,
  DataTable,
  ConfirmDialog,
  Modal,
  AudioPlayer,
  Select,
} from '../components';
import type { ColumnDef } from '../components/DataTable/DataTable';
import { historyService, type HistoryItem } from '../services';

export type HistoryType = 'Text to Speech' | 'Long-form' | 'Voice Clone';
export type HistoryStatus = 'COMPLETED' | 'FAILED' | 'CANCELLED';

export const HistoryPage: React.FC = () => {
  const navigate = useNavigate();

  const [historyItems, setHistoryItems] = useState<HistoryItem[]>([]);

  useEffect(() => {
    historyService.getHistory().then(setHistoryItems);
  }, []);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedTypeFilter, setSelectedTypeFilter] = useState('ALL');
  const [selectedDateFilter, setSelectedDateFilter] = useState<'ALL' | 'today' | 'week' | 'month'>('ALL');

  // Audio Play modal
  const [playingItem, setPlayingItem] = useState<HistoryItem | null>(null);

  // Delete confirmation
  const [deleteTarget, setDeleteTarget] = useState<HistoryItem | null>(null);

  // Filter options
  const typeFilterOptions = useMemo(() => {
    return [
      { id: 'ALL', label: 'Tất cả', count: historyItems.length },
      { id: 'Text to Speech', label: 'Text to Speech', count: historyItems.filter((h) => h.type === 'Text to Speech').length },
      { id: 'Long-form', label: 'Long-form', count: historyItems.filter((h) => h.type === 'Long-form').length },
      { id: 'Voice Clone', label: 'Voice Clone', count: historyItems.filter((h) => h.type === 'Voice Clone').length },
    ];
  }, [historyItems]);

  // Filtered dataset
  const filteredHistory = useMemo(() => {
    return historyItems.filter((item) => {
      const matchesSearch =
        searchQuery.trim() === '' ||
        item.textPreview.toLowerCase().includes(searchQuery.toLowerCase()) ||
        item.voice.toLowerCase().includes(searchQuery.toLowerCase()) ||
        item.type.toLowerCase().includes(searchQuery.toLowerCase());

      const matchesType =
        selectedTypeFilter === 'ALL' || item.type === selectedTypeFilter;

      const matchesDate =
        selectedDateFilter === 'ALL' ||
        item.dateCategory === selectedDateFilter ||
        (selectedDateFilter === 'month' && (item.dateCategory === 'week' || item.dateCategory === 'today'));

      return matchesSearch && matchesType && matchesDate;
    });
  }, [historyItems, searchQuery, selectedTypeFilter, selectedDateFilter]);

  const handleConfirmDelete = () => {
    if (!deleteTarget) return;
    setHistoryItems((prev) => prev.filter((h) => h.id !== deleteTarget.id));
    setDeleteTarget(null);
  };

  const handleRegenerate = (_item: HistoryItem) => {
    navigate('/tts');
  };

  // DataTable columns
  const columns: ColumnDef<HistoryItem>[] = [
    {
      key: 'date',
      header: 'Thời gian (Date)',
      width: '140px',
      render: (item) => (
        <span style={{ fontSize: '12px', color: 'var(--neutral-600)', fontFamily: 'var(--font-family-mono)' }}>
          {item.date}
        </span>
      ),
    },
    {
      key: 'type',
      header: 'Loại (Type)',
      width: '130px',
      render: (item) => (
        <StatusBadge
          status={
            item.type === 'Text to Speech'
              ? 'info'
              : item.type === 'Long-form'
              ? 'neutral'
              : 'warning'
          }
          label={item.type}
          size="sm"
          showDot={false}
        />
      ),
    },
    {
      key: 'textPreview',
      header: 'Trích đoạn văn bản (Text Preview)',
      render: (item) => (
        <span
          style={{
            fontSize: '13px',
            color: 'var(--neutral-800)',
            lineHeight: '1.5',
            display: 'block',
            maxWidth: '380px',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
          title={item.textPreview}
        >
          {item.textPreview}
        </span>
      ),
    },
    {
      key: 'voice',
      header: 'Giọng đọc (Voice)',
      width: '170px',
      render: (item) => (
        <span style={{ fontSize: '13px', color: 'var(--neutral-700)' }}>
          {item.voice}
        </span>
      ),
    },
    {
      key: 'duration',
      header: 'Thời lượng',
      width: '100px',
      render: (item) => (
        <span style={{ fontSize: '12px', fontFamily: 'var(--font-family-mono)', color: 'var(--neutral-600)' }}>
          {item.duration}
        </span>
      ),
    },
    {
      key: 'status',
      header: 'Trạng thái',
      width: '120px',
      render: (item) => (
        <StatusBadge
          status={
            item.status === 'COMPLETED'
              ? 'success'
              : item.status === 'CANCELLED'
              ? 'warning'
              : 'error'
          }
          label={item.status}
          size="sm"
        />
      ),
    },
    {
      key: 'actions',
      header: 'Hành động',
      width: '200px',
      align: 'right',
      render: (item) => (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '4px' }}>
          {item.status === 'COMPLETED' && (
            <Button
              size="sm"
              variant="outline"
              onClick={() => setPlayingItem(item)}
              iconLeft={
                <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
                  <polygon points="5 3 19 12 5 21 5 3"></polygon>
                </svg>
              }
            >
              Play
            </Button>
          )}

          <Button
            size="sm"
            variant="ghost"
            onClick={() => navigate(item.route)}
          >
            Open
          </Button>

          <Button
            size="sm"
            variant="ghost"
            title="Tạo lại"
            onClick={() => handleRegenerate(item)}
          >
            Regenerate
          </Button>

          <Button
            size="sm"
            variant="ghost"
            style={{ color: 'var(--danger-text)' }}
            title="Xóa bản ghi"
            onClick={() => setDeleteTarget(item)}
          >
            Xóa
          </Button>
        </div>
      ),
    },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Top Header */}
      <div>
        <h1 style={{ fontSize: '20px', fontWeight: 700, color: 'var(--neutral-900)' }}>
          History (Lịch sử tác vụ âm thanh)
        </h1>
        <p style={{ fontSize: '13px', color: 'var(--neutral-500)', marginTop: '2px' }}>
          Nhật ký audit các lượt tổng hợp giọng nói, xuất tệp và nhân bản offline
        </p>
      </div>

      {/* Filter, Search & Date Filter Bar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
          <SearchInput
            value={searchQuery}
            onChange={setSearchQuery}
            placeholder="Tìm theo trích đoạn, giọng đọc..."
          />

          <div style={{ width: '160px' }}>
            <Select
              options={[
                { value: 'ALL', label: 'Toàn bộ thời gian' },
                { value: 'today', label: 'Hôm nay' },
                { value: 'week', label: '7 ngày qua' },
                { value: 'month', label: '30 ngày qua' },
              ]}
              value={selectedDateFilter}
              onChange={(e) => setSelectedDateFilter(e.target.value as any)}
            />
          </div>
        </div>

        <FilterBar
          options={typeFilterOptions}
          activeId={selectedTypeFilter}
          onSelect={setSelectedTypeFilter}
        />
      </div>

      {/* History DataTable */}
      <DataTable
        columns={columns}
        data={filteredHistory}
        keyExtractor={(item) => item.id}
        emptyTitle="Không có lịch sử tác vụ"
        emptyDescription="Chưa có tác vụ tổng hợp giọng nói nào khớp với bộ lọc thời gian và từ khóa."
      />

      {/* Play Audio Modal */}
      <Modal
        isOpen={Boolean(playingItem)}
        onClose={() => setPlayingItem(null)}
        title="Nghe lại âm thanh lịch sử"
        size="md"
        footer={
          <Button variant="outline" size="md" onClick={() => setPlayingItem(null)}>
            Đóng
          </Button>
        }
      >
        {playingItem && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div style={{ padding: '10px 12px', background: 'var(--neutral-50)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-default)', fontSize: '13px', color: 'var(--neutral-700)' }}>
              <strong>Văn bản đọc:</strong> {playingItem.textPreview}
            </div>

            <AudioPlayer
              title={`Exported Track: ${playingItem.type}`}
              duration={18.4}
              voice={playingItem.voice}
              language={playingItem.language}
            />
          </div>
        )}
      </Modal>

      {/* Delete Confirmation Dialog */}
      <ConfirmDialog
        isOpen={Boolean(deleteTarget)}
        onClose={() => setDeleteTarget(null)}
        onConfirm={handleConfirmDelete}
        title="Xóa nhật ký tác vụ"
        message={`Bạn có chắc chắn muốn xóa bản ghi lịch sử ngày ${deleteTarget?.date || ''}? Tệp âm thanh đã xuất có thể không còn phát lại được từ lịch sử.`}
        confirmLabel="Xóa bản ghi"
        isDestructive
      />
    </div>
  );
};
