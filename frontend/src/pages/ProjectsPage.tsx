import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Button,
  StatusBadge,
  ProgressBar,
  SearchInput,
  FilterBar,
  DataTable,
  ConfirmDialog,
  Modal,
  Input,
} from '../components';
import type { ColumnDef } from '../components/DataTable/DataTable';
import { projectService, type ProjectItem } from '../services';

export type ProjectStatus = 'RUNNING' | 'PAUSED' | 'COMPLETED' | 'FAILED';
export type ProjectType = 'Text to Speech' | 'Long-form' | 'Voice Clone';

export const ProjectsPage: React.FC = () => {
  const navigate = useNavigate();

  const [projects, setProjects] = useState<ProjectItem[]>([]);

  useEffect(() => {
    projectService.getProjects().then(setProjects);
  }, []);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedStatusFilter, setSelectedStatusFilter] = useState<string>('ALL');

  // Modals & confirmation state
  const [renameProject, setRenameProject] = useState<ProjectItem | null>(null);
  const [newName, setNewName] = useState('');
  const [deleteTarget, setDeleteTarget] = useState<ProjectItem | null>(null);

  // Status filters
  const filterOptions = useMemo(() => {
    return [
      { id: 'ALL', label: 'Tất cả', count: projects.length },
      { id: 'RUNNING', label: 'Running', count: projects.filter((p) => p.status === 'RUNNING').length },
      { id: 'PAUSED', label: 'Paused', count: projects.filter((p) => p.status === 'PAUSED').length },
      { id: 'COMPLETED', label: 'Completed', count: projects.filter((p) => p.status === 'COMPLETED').length },
      { id: 'FAILED', label: 'Failed', count: projects.filter((p) => p.status === 'FAILED').length },
    ];
  }, [projects]);

  // Filtered dataset
  const filteredProjects = useMemo(() => {
    return projects.filter((p) => {
      const matchesSearch =
        searchQuery.trim() === '' ||
        p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        p.voice.toLowerCase().includes(searchQuery.toLowerCase()) ||
        p.type.toLowerCase().includes(searchQuery.toLowerCase());

      const matchesStatus =
        selectedStatusFilter === 'ALL' || p.status === selectedStatusFilter;

      return matchesSearch && matchesStatus;
    });
  }, [projects, searchQuery, selectedStatusFilter]);

  // Actions
  const handleTogglePause = (proj: ProjectItem) => {
    setProjects((prev) =>
      prev.map((p) => {
        if (p.id === proj.id) {
          const nextStatus = p.status === 'PAUSED' ? 'RUNNING' : 'PAUSED';
          return { ...p, status: nextStatus };
        }
        return p;
      })
    );
  };

  const handleConfirmRename = () => {
    if (!renameProject || !newName.trim()) return;
    setProjects((prev) =>
      prev.map((p) => (p.id === renameProject.id ? { ...p, name: newName.trim() } : p))
    );
    setRenameProject(null);
  };

  const handleConfirmDelete = () => {
    if (!deleteTarget) return;
    setProjects((prev) => prev.filter((p) => p.id !== deleteTarget.id));
    setDeleteTarget(null);
  };

  // DataTable Columns
  const columns: ColumnDef<ProjectItem>[] = [
    {
      key: 'name',
      header: 'Dự án (Project)',
      render: (item) => (
        <div>
          <button
            type="button"
            onClick={() => navigate(item.route)}
            style={{
              background: 'none',
              border: 'none',
              padding: 0,
              fontSize: '14px',
              fontWeight: 600,
              color: 'var(--neutral-900)',
              cursor: 'pointer',
              textAlign: 'left',
            }}
          >
            {item.name}
          </button>
          <span style={{ display: 'block', fontSize: '11px', color: 'var(--neutral-400)', marginTop: '2px' }}>
            ID: {item.id}
          </span>
        </div>
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
      key: 'voice',
      header: 'Giọng đọc (Voice)',
      width: '180px',
      render: (item) => (
        <span style={{ fontSize: '13px', color: 'var(--neutral-700)' }}>
          {item.voice}
        </span>
      ),
    },
    {
      key: 'language',
      header: 'Ngôn ngữ',
      width: '110px',
      render: (item) => (
        <span style={{ fontSize: '12px', color: 'var(--neutral-600)' }}>
          {item.language}
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
              : item.status === 'RUNNING'
              ? 'info'
              : item.status === 'PAUSED'
              ? 'warning'
              : 'error'
          }
          label={item.status}
          size="sm"
        />
      ),
    },
    {
      key: 'progress',
      header: 'Tiến độ',
      width: '140px',
      render: (item) => (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: 'var(--neutral-500)' }}>
            <span>{item.progress}%</span>
          </div>
          <ProgressBar
            value={item.progress}
            size="sm"
            status={item.status === 'COMPLETED' ? 'success' : item.status === 'FAILED' ? 'error' : 'default'}
          />
        </div>
      ),
    },
    {
      key: 'updatedAt',
      header: 'Cập nhật',
      width: '110px',
      render: (item) => (
        <span style={{ fontSize: '12px', color: 'var(--neutral-500)' }}>
          {item.updatedAt}
        </span>
      ),
    },
    {
      key: 'actions',
      header: 'Hành động',
      width: '190px',
      align: 'right',
      render: (item) => (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '4px' }}>
          <Button
            size="sm"
            variant="outline"
            onClick={() => navigate(item.route)}
          >
            Open
          </Button>

          {(item.status === 'RUNNING' || item.status === 'PAUSED') && (
            <Button
              size="sm"
              variant="ghost"
              onClick={() => handleTogglePause(item)}
            >
              {item.status === 'PAUSED' ? 'Resume' : 'Pause'}
            </Button>
          )}

          <Button
            size="sm"
            variant="ghost"
            title="Đổi tên dự án"
            onClick={() => {
              setRenameProject(item);
              setNewName(item.name);
            }}
          >
            Đổi tên
          </Button>

          <Button
            size="sm"
            variant="ghost"
            style={{ color: 'var(--danger-text)' }}
            title="Xóa dự án"
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
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h1 style={{ fontSize: '20px', fontWeight: 700, color: 'var(--neutral-900)' }}>
            Projects (Quản lý dự án)
          </h1>
          <p style={{ fontSize: '13px', color: 'var(--neutral-500)', marginTop: '2px' }}>
            Theo dõi tất cả tác vụ chuyển đổi giọng nói, sách dài và hồ sơ voice clone
          </p>
        </div>

        <div style={{ display: 'flex', gap: '8px' }}>
          <Button
            variant="outline"
            size="md"
            onClick={() => navigate('/tts')}
          >
            + New TTS
          </Button>
          <Button
            variant="primary"
            size="md"
            onClick={() => navigate('/long-form')}
          >
            + New Long-form
          </Button>
        </div>
      </div>

      {/* Filter & Search Bar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
        <SearchInput
          value={searchQuery}
          onChange={setSearchQuery}
          placeholder="Tìm tên dự án, giọng đọc, phân loại..."
        />

        <FilterBar
          options={filterOptions}
          activeId={selectedStatusFilter}
          onSelect={setSelectedStatusFilter}
        />
      </div>

      {/* Projects Table */}
      <DataTable
        columns={columns}
        data={filteredProjects}
        keyExtractor={(item) => item.id}
        emptyTitle="Không tìm thấy dự án nào"
        emptyDescription="Thử thay đổi bộ lọc trạng thái hoặc từ khóa tìm kiếm."
      />

      {/* Rename Modal */}
      <Modal
        isOpen={Boolean(renameProject)}
        onClose={() => setRenameProject(null)}
        title="Đổi tên dự án"
        size="sm"
        footer={
          <>
            <Button variant="outline" size="md" onClick={() => setRenameProject(null)}>
              Hủy
            </Button>
            <Button variant="primary" size="md" onClick={handleConfirmRename}>
              Lưu tên
            </Button>
          </>
        }
      >
        <Input
          label="Tên dự án mới"
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          placeholder="Nhập tên mới..."
        />
      </Modal>

      {/* Delete Confirmation */}
      <ConfirmDialog
        isOpen={Boolean(deleteTarget)}
        onClose={() => setDeleteTarget(null)}
        onConfirm={handleConfirmDelete}
        title="Xóa dự án"
        message={`Bạn có chắc chắn muốn xóa dự án "${deleteTarget?.name || ''}"? Dữ liệu âm thanh và các chunk liên quan sẽ bị xóa khỏi bộ nhớ.`}
        confirmLabel="Xóa dự án"
        isDestructive
      />
    </div>
  );
};
