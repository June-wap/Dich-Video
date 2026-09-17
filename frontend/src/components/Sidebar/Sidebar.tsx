import React, { useEffect, useState } from 'react';
import { NavLink } from 'react-router-dom';
import { useT } from '../../i18n';
import { systemService, type SystemStatus } from '../../services/systemService';
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
      {
        to: '/diagnostics',
        labelKey: 'nav.diagnostics',
        icon: (
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
          </svg>
        ),
      },
    ],
  },
];

export const Sidebar: React.FC = () => {
  const { t } = useT();
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [version, setVersion] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    systemService
      .status()
      .then((data) => {
        if (!cancelled) setStatus(data);
      })
      .catch(() => {
        // Real status is a nice-to-have here (Diagnostics is the page of
        // record for failures) - silently keep the "unknown" placeholder
        // rather than showing an error state in the nav rail.
      });
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

  const omnivoiceReady = status?.omnivoice_available && status.omnivoice_model_loaded;

  return (
    <aside className="ds-sidebar">
      {/* Brand Header */}
      <NavLink to="/" className="ds-sidebar-brand" style={{ textDecoration: 'none' }}>
        <div className="ds-sidebar-brand-icon">V</div>
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

      {/* BOTTOM STATUS - real data from GET /api/system/status (was
          hardcoded "RTX 4050" / "Ready" / "Prototype" for every machine). */}
      <div className="ds-sidebar-status-panel">
        <div className="ds-sidebar-status-row">
          <span>{t('sidebar.status.omnivoice')}</span>
          <span className="ds-sidebar-status-value">
            <span className="ds-sidebar-status-dot" aria-hidden="true" />
            {status == null ? t('sidebar.status.unknown') : omnivoiceReady ? t('sidebar.status.ready') : t('sidebar.status.notReady')}
          </span>
        </div>
        <div className="ds-sidebar-status-row">
          <span>{t('sidebar.status.gpu')}</span>
          <span className="ds-sidebar-status-value">
            {status == null ? '—' : status.gpu_name ?? t('sidebar.status.notDetected')}
          </span>
        </div>
        <div className="ds-sidebar-status-row">
          <span>{t('sidebar.status.version')}</span>
          <span className="ds-sidebar-status-value">{version ? `v${version}` : '—'}</span>
        </div>
      </div>
    </aside>
  );
};
