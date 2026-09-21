import React, { useEffect, useState } from 'react';
import { NavLink } from 'react-router-dom';
import { useT } from '../../i18n';
import { healthService } from '../../services/healthService';

interface NavItem {
  to: string;
  labelKey: string;
  icon: React.ReactNode;
}

interface NavSection {
  titleKey: string;
  items: NavItem[];
}

const NAV_SECTIONS: NavSection[] = [
  {
    titleKey: 'nav.section.create',
    items: [
      {
        to: '/tts',
        labelKey: 'nav.tts',
        icon: (
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon>
            <path d="M15.54 8.46a5 5 0 0 1 0 7.07"></path>
            <path d="M19.07 4.93a10 10 0 0 1 0 14.14"></path>
          </svg>
        ),
      },
      {
        to: '/clone',
        labelKey: 'nav.clone',
        icon: (
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"></path>
            <path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
            <line x1="12" x2="12" y1="19" y2="22"></line>
          </svg>
        ),
      },
    ],
  },
  {
    titleKey: 'nav.section.library',
    items: [
      {
        to: '/voices',
        labelKey: 'nav.voices',
        icon: (
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
            <circle cx="9" cy="7" r="4"></circle>
            <path d="M23 21v-2a4 4 0 0 0-3-3.87"></path>
            <path d="M16 3.13a4 4 0 0 1 0 7.75"></path>
          </svg>
        ),
      },
    ],
  },
  {
    titleKey: 'nav.section.activity',
    items: [
      {
        to: '/history',
        labelKey: 'nav.history',
        icon: (
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10"></circle>
            <polyline points="12 6 12 12 16 14"></polyline>
          </svg>
        ),
      },
    ],
  },
  {
    titleKey: 'nav.section.system',
    items: [
      {
        to: '/settings',
        labelKey: 'nav.settings',
        icon: (
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="3"></circle>
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
          </svg>
        ),
      },
      // Diagnostics (17/09): gỡ khỏi nav theo yêu cầu - không muốn khách
      // hàng nhìn thấy tên/trạng thái provider đang chạy phía sau.
      // Route trong App.tsx cũng đã gỡ theo (không chỉ ẩn link) để không ai
      // vào được bằng cách gõ thẳng /diagnostics - xem ghi chú ở đó.
    ],
  },
];

export const Sidebar: React.FC = () => {
  const { t } = useT();
  const [version, setVersion] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    healthService
      .get()
      .then((data) => {
        if (!cancelled) setVersion(data.version);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <aside className="ds-sidebar">
      {/* Brand Header */}
      <NavLink to="/" className="ds-sidebar-brand" style={{ textDecoration: 'none' }}>
        <img src="/logo-128.png" alt="Voca Basic" className="ds-sidebar-brand-icon" style={{ objectFit: 'cover', background: 'transparent' }} />
        <span className="ds-sidebar-brand-text">{t('app.brand')}</span>
      </NavLink>

      {/* Navigation Sections */}
      <nav className="ds-sidebar-nav">
        {/* Dashboard quick link */}
        <div className="ds-sidebar-section">
          <NavLink
            to="/"
            end
            className={({ isActive }) => `ds-sidebar-link ${isActive ? 'ds-sidebar-link--active' : ''}`}
          >
            <span className="ds-sidebar-item-icon">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="3" width="7" height="7" rx="1"></rect>
                <rect x="14" y="3" width="7" height="7" rx="1"></rect>
                <rect x="14" y="14" width="7" height="7" rx="1"></rect>
                <rect x="3" y="14" width="7" height="7" rx="1"></rect>
              </svg>
            </span>
            <span>{t('nav.dashboard')}</span>
          </NavLink>
        </div>

        {/* Grouped Sections */}
        {NAV_SECTIONS.map((section) => (
          <div key={section.titleKey} className="ds-sidebar-section">
            <span className="ds-sidebar-section-title">{t(section.titleKey)}</span>
            {section.items.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) => `ds-sidebar-link ${isActive ? 'ds-sidebar-link--active' : ''}`}
              >
                <span className="ds-sidebar-item-icon">{item.icon}</span>
                <span>{t(item.labelKey)}</span>
              </NavLink>
            ))}
          </div>
        ))}
      </nav>

      {/* BOTTOM STATUS (17/09): chỉ còn phiên bản ứng dụng - đã bỏ hẳn dòng
          tên/trạng thái provider và tên GPU/phần cứng theo yêu cầu,
          không muốn lộ ra cho khách hàng đang chạy model/thiết bị gì phía
          sau. Diagnostics (đã gỡ khỏi nav + route ở trên/App.tsx) vẫn là nơi
          duy nhất còn xem được các chi tiết đó, và giờ cũng không ai vào
          được nữa qua giao diện. */}
      <div className="ds-sidebar-status-panel">
        <div className="ds-sidebar-status-row">
          <span>{t('sidebar.status.version')}</span>
          <span className="ds-sidebar-status-value">{version ? `v${version}` : '—'}</span>
        </div>
      </div>
    </aside>
  );
};
