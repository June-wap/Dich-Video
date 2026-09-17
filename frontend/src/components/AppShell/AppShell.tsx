import React from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { Sidebar } from '../Sidebar/Sidebar';

const ROUTE_NAMES: Record<string, string> = {
  '/': 'Dashboard',
  '/tts': 'Text to Speech',
  '/clone': 'Voice Cloning',
  '/voices': 'Voice Library',
  '/history': 'History',
  '/settings': 'Settings',
  '/diagnostics': 'Diagnostics',
};

export const AppShell: React.FC = () => {
  const location = useLocation();
  const pageTitle = ROUTE_NAMES[location.pathname] ?? 'Workspace';

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
