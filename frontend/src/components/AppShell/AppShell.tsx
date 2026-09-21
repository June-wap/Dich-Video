import React, { useEffect, useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { Sidebar } from '../Sidebar/Sidebar';
import { LicenseActivationModal } from '../License/LicenseActivationModal';
import { licenseService, type LicenseStatusResponse } from '../../services/licenseService';

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

  const [licenseData, setLicenseData] = useState<LicenseStatusResponse | null>(null);
  const [modalOpen, setModalOpen] = useState(false);

  const fetchLicense = () => {
    licenseService.getStatus()
      .then((data) => setLicenseData(data))
      .catch(() => {});
  };

  useEffect(() => {
    fetchLicense();
  }, []);

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

          <div className="ds-topbar-actions" style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            {/* License Status Badge */}
            {licenseData && (
              <button
                type="button"
                onClick={() => setModalOpen(true)}
                title="Bấm để xem chi tiết hoặc kích hoạt bản quyền"
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '4px 10px',
                  borderRadius: '16px',
                  fontSize: '12px',
                  fontWeight: 600,
                  cursor: 'pointer',
                  border: '1px solid',
                  backgroundColor: licenseData.is_active
                    ? 'var(--success-50, #f0fdf4)'
                    : 'var(--danger-50, #fef2f2)',
                  borderColor: licenseData.is_active
                    ? 'var(--success-200, #bbf7d0)'
                    : 'var(--danger-200, #fecaca)',
                  color: licenseData.is_active
                    ? 'var(--success-700, #15803d)'
                    : 'var(--danger-700, #b91c1c)',
                  transition: 'all 0.15s ease',
                }}
              >
                <span>{licenseData.is_active ? '🛡️' : '⚠️'}</span>
                <span>
                  {licenseData.is_active
                    ? licenseData.is_trial
                      ? `Dùng thử: Còn ${licenseData.time_left_str ?? '1 giờ'}`
                      : licenseData.license_type === 'lifetime'
                      ? 'Bản quyền: Vĩnh viễn'
                      : `Bản quyền: Còn ${licenseData.time_left_str ?? `${licenseData.days_left ?? 0} ngày`}`
                    : 'Chưa kích hoạt bản quyền'}
                </span>
              </button>
            )}

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

      {/* License Activation Modal */}
      <LicenseActivationModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        statusData={licenseData}
        onActivated={(status) => setLicenseData(status)}
      />
    </div>
  );
};

