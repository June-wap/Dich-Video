import React from 'react';
import { Link } from 'react-router-dom';
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  StatusBadge,
  ProgressBar,
} from '../components';

interface RecentProject {
  id: string;
  name: string;
  type: 'Text to Speech' | 'Long-form' | 'Voice Clone';
  voice: string;
  progress: number;
  status: 'COMPLETED' | 'IN_PROGRESS' | 'QUEUED';
  updatedAt: string;
  route: string;
}

const RECENT_PROJECTS: RecentProject[] = [
  {
    id: 'proj-001',
    name: 'Audiobook - Chương 1: Bình minh trên thảo nguyên',
    type: 'Long-form',
    voice: 'vi-VN - Hoài My (Nữ)',
    progress: 100,
    status: 'COMPLETED',
    updatedAt: '10 phút trước',
    route: '/long-form/proj-001',
  },
  {
    id: 'proj-002',
    name: 'Lời chào tiếp thị sản phẩm OmniVoice v1',
    type: 'Text to Speech',
    voice: 'vi-VN - Nam Anh (Nam)',
    progress: 100,
    status: 'COMPLETED',
    updatedAt: '35 phút trước',
    route: '/tts',
  },
  {
    id: 'proj-003',
    name: 'Clone giọng đọc bản tin thời sự 19h',
    type: 'Voice Clone',
    voice: 'Custom - Speaker Zero-Shot',
    progress: 75,
    status: 'IN_PROGRESS',
    updatedAt: '2 giờ trước',
    route: '/clone',
  },
  {
    id: 'proj-004',
    name: 'Kịch bản hội thoại đa nhân vật song ngữ Anh-Việt',
    type: 'Long-form',
    voice: 'Jenny & Mai Thảo',
    progress: 40,
    status: 'IN_PROGRESS',
    updatedAt: 'Hôm qua',
    route: '/long-form/proj-004',
  },
  {
    id: 'proj-005',
    name: 'Podcast Công nghệ AI & Tương lai âm thanh',
    type: 'Long-form',
    voice: 'vi-VN - Quốc Bảo',
    progress: 0,
    status: 'QUEUED',
    updatedAt: '3 ngày trước',
    route: '/long-form/proj-005',
  },
];

export const DashboardPage: React.FC = () => {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* 1. Header & System Compact Status */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h1 style={{ fontSize: '24px', fontWeight: 700, color: 'var(--neutral-900)', letterSpacing: '-0.02em' }}>
            Xin chào
          </h1>
          <p style={{ fontSize: '15px', color: 'var(--neutral-500)', marginTop: '4px' }}>
            Bạn muốn tạo gì hôm nay?
          </p>
        </div>

        {/* System compact status bar */}
        <div className="ds-system-compact-bar">
          <div className="ds-system-compact-items">
            <span className="ds-system-pill ds-system-pill--success">
              <span className="ds-sidebar-status-dot" aria-hidden="true" />
              OmniVoice Ready
            </span>
            <span className="ds-system-pill">
              GPU RTX 4050
            </span>
            <span className="ds-system-pill ds-system-pill--success">
              CUDA Available
            </span>
          </div>
        </div>
      </div>

      {/* 2. Action cards (4 items, each navigates correctly) */}
      <div className="ds-action-cards-grid">
        {/* 1. Text to Speech */}
        <Link to="/tts" className="ds-action-card">
          <div className="ds-action-card-icon-wrapper">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon>
              <path d="M15.54 8.46a5 5 0 0 1 0 7.07"></path>
              <path d="M19.07 4.93a10 10 0 0 1 0 14.14"></path>
            </svg>
          </div>
          <h2 className="ds-action-card-title">Text to Speech</h2>
          <p className="ds-action-card-desc">
            Chuyển đổi văn bản thành giọng nói tức thì với các giọng đọc bản ngữ chất lượng cao.
          </p>
          <div className="ds-action-card-footer">
            <span>Bắt đầu tạo</span>
            <span>→</span>
          </div>
        </Link>

        {/* 2. Long-form Studio */}
        <Link to="/long-form" className="ds-action-card">
          <div className="ds-action-card-icon-wrapper">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path>
              <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path>
            </svg>
          </div>
          <h2 className="ds-action-card-title">Long-form Studio</h2>
          <p className="ds-action-card-desc">
            Sản xuất sách nói, truyện dài tập, phân đoạn kịch bản và xuất file master nhiều chương.
          </p>
          <div className="ds-action-card-footer">
            <span>Mở Studio</span>
            <span>→</span>
          </div>
        </Link>

        {/* 3. Voice Cloning */}
        <Link to="/clone" className="ds-action-card">
          <div className="ds-action-card-icon-wrapper">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"></path>
              <path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
              <line x1="12" y1="19" x2="12" y2="22"></line>
            </svg>
          </div>
          <h2 className="ds-action-card-title">Voice Cloning</h2>
          <p className="ds-action-card-desc">
            Nhân bản giọng nói từ mẫu thu âm mẫu ngắn (zero-shot cloning) chạy cục bộ không gửi mạng.
          </p>
          <div className="ds-action-card-footer">
            <span>Tạo mẫu giọng</span>
            <span>→</span>
          </div>
        </Link>

        {/* 4. Voice Library */}
        <Link to="/voices" className="ds-action-card">
          <div className="ds-action-card-icon-wrapper">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
              <circle cx="9" cy="7" r="4"></circle>
              <path d="M23 21v-2a4 4 0 0 0-3-3.87"></path>
              <path d="M16 3.13a4 4 0 0 1 0 7.75"></path>
            </svg>
          </div>
          <h2 className="ds-action-card-title">Voice Library</h2>
          <p className="ds-action-card-desc">
            Kho quản lý các mô hình giọng nói đã cài đặt, tải thêm model hoặc cấu hình voice profile.
          </p>
          <div className="ds-action-card-footer">
            <span>Khám phá thư viện</span>
            <span>→</span>
          </div>
        </Link>
      </div>

      {/* 3. Recent Projects table */}
      <Card>
        <CardHeader style={{ display: 'flex', flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <CardTitle>Dự án gần đây</CardTitle>
            <CardDescription>Danh sách các tác vụ tạo giọng nói và dự án vừa cập nhật</CardDescription>
          </div>
          <Link
            to="/projects"
            style={{ fontSize: '13px', color: 'var(--color-primary-600)', fontWeight: 500 }}
          >
            Xem tất cả dự án →
          </Link>
        </CardHeader>

        <CardContent style={{ padding: 0 }}>
          <div className="ds-table-wrapper" style={{ border: 'none', borderRadius: 0, boxShadow: 'none' }}>
            <table className="ds-table">
              <thead>
                <tr>
                  <th className="ds-th">Tên</th>
                  <th className="ds-th">Loại</th>
                  <th className="ds-th">Giọng</th>
                  <th className="ds-th" style={{ width: '180px' }}>Tiến độ</th>
                  <th className="ds-th">Cập nhật</th>
                </tr>
              </thead>
              <tbody>
                {RECENT_PROJECTS.map((proj) => (
                  <tr key={proj.id} className="ds-tr">
                    <td className="ds-td">
                      <Link
                        to={proj.route}
                        style={{ color: 'var(--neutral-900)', fontWeight: 600, display: 'block' }}
                      >
                        {proj.name}
                      </Link>
                    </td>
                    <td className="ds-td">
                      <StatusBadge
                        status={
                          proj.type === 'Text to Speech'
                            ? 'info'
                            : proj.type === 'Long-form'
                            ? 'neutral'
                            : 'warning'
                        }
                        label={proj.type}
                        size="sm"
                        showDot={false}
                      />
                    </td>
                    <td className="ds-td">
                      <span style={{ fontSize: '13px', color: 'var(--neutral-700)' }}>{proj.voice}</span>
                    </td>
                    <td className="ds-td">
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: 'var(--neutral-500)' }}>
                          <span>{proj.status}</span>
                          <span>{proj.progress}%</span>
                        </div>
                        <ProgressBar
                          value={proj.progress}
                          size="sm"
                          status={proj.status === 'COMPLETED' ? 'success' : 'default'}
                        />
                      </div>
                    </td>
                    <td className="ds-td">
                      <span style={{ fontSize: '12px', color: 'var(--neutral-500)' }}>{proj.updatedAt}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};
