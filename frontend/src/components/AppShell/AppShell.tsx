import React from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { Sidebar } from '../Sidebar/Sidebar';

const ROUTE_NAMES: Record<string, string> = {
  '/': 'Dashboard',
  '/tts': 'Text to Speech',
  '/long-form': 'Long-form Studio',
  '/clone': 'Voice Cloning',
  '/voices': 'Voice Library',
  '/projects': 'Projects',
  '/history': 'History',
  '/settings': 'Settings',
  '/diagnostics': 'Diagnostics',
  '/showcase': 'Design System Showcase',
};

export const AppShell: React.FC = () => {
  const location = useLocation();

  // Handle dynamic route matching for /long-form/:id
  const getPageTitle = (pathname: string): string => {
    if (ROUTE_NAMES[pathname]) {
      return ROUTE_NAMES[pathname];
    }
    if (pathname.startsWith('/long-form/')) {
      const id = pathname.replace('/long-form/', '');
      return `Project Detail: ${id}`;
    }
    return 'Workspace';
  };

  const pageTitle = getPageTitle(location.pathname);

  return (
    <div className="ds-app-layout">
      {/* 1. Persistent Sidebar */}
      <Sidebar />

      {/* 2. Workspace & Main Content Area */}
      <div className="ds-workspace-container">
        {/* Topbar */}
        <header className="ds-topbar">
          <div className="ds-topbar-title-group">
            <h1 className="ds-topbar-title">{pageTitle}</h1>
            <span className="ds-topbar-meta">Local Offline Engine</span>
          </div>

          <div className="ds-topbar-actions">
            <span style={{ fontSize: '12px', color: 'var(--neutral-500)' }}>
              1366 × 768+ Desktop Ready
            </span>
          </div>
        </header>

        {/* Scrollable Main Content */}
        <main className="ds-main-content">
          <div className="ds-content-container">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
};
