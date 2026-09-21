import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useT } from '../i18n';
import { systemService, type SystemStatus } from '../services/systemService';

export const DashboardPage: React.FC = () => {
  const { t } = useT();
  const [status, setStatus] = useState<SystemStatus | null>(null);

  useEffect(() => {
    let cancelled = false;
    systemService
      .status()
      .then((data) => {
        if (!cancelled) setStatus(data);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  const providerReady = Boolean(status?.primary_provider && status.provider_state === 'READY');

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* 1. Header & System Compact Status */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h1 style={{ fontSize: '24px', fontWeight: 700, color: 'var(--neutral-900)', letterSpacing: '-0.02em' }}>
            {t('dashboard.greeting')}
          </h1>
          <p style={{ fontSize: '15px', color: 'var(--neutral-500)', marginTop: '4px' }}>
            {t('dashboard.subtitle')}
          </p>
        </div>

        {/* System compact status bar - real data from GET /api/system/status
            (was hardcoded "RTX 4050" / "CUDA Available" for every machine). */}
        {status && (
          <div className="ds-system-compact-bar">
            <div className="ds-system-compact-items">
              <span className={`ds-system-pill ${providerReady ? 'ds-system-pill--success' : ''}`}>
                <span className="ds-sidebar-status-dot" aria-hidden="true" />
                {providerReady ? 'TTS provider ready' : 'No TTS provider available'}
              </span>
              {status.gpu_name && <span className="ds-system-pill">{status.gpu_name}</span>}
              <span className={`ds-system-pill ${status.cuda_available ? 'ds-system-pill--success' : ''}`}>
                {status.cuda_available ? t('dashboard.status.cudaAvailable') : t('dashboard.status.cudaUnavailable')}
              </span>
            </div>
          </div>
        )}
      </div>

      {/* 2. Action cards (3 items — Short TTS + Voice Cloning scope, Long-form Studio removed) */}
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
          <h2 className="ds-action-card-title">{t('dashboard.card.tts.title')}</h2>
          <p className="ds-action-card-desc">{t('dashboard.card.tts.desc')}</p>
          <div className="ds-action-card-footer">
            <span>{t('dashboard.card.tts.cta')}</span>
          </div>
        </Link>

        {/* 2. Voice Cloning */}
        <Link to="/clone" className="ds-action-card">
          <div className="ds-action-card-icon-wrapper">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"></path>
              <path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
              <line x1="12" y1="19" x2="12" y2="22"></line>
            </svg>
          </div>
          <h2 className="ds-action-card-title">{t('dashboard.card.clone.title')}</h2>
          <p className="ds-action-card-desc">{t('dashboard.card.clone.desc')}</p>
          <div className="ds-action-card-footer">
            <span>{t('dashboard.card.clone.cta')}</span>
          </div>
        </Link>

        {/* 3. Voice Library */}
        <Link to="/voices" className="ds-action-card">
          <div className="ds-action-card-icon-wrapper">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
              <circle cx="9" cy="7" r="4"></circle>
              <path d="M23 21v-2a4 4 0 0 0-3-3.87"></path>
              <path d="M16 3.13a4 4 0 0 1 0 7.75"></path>
            </svg>
          </div>
          <h2 className="ds-action-card-title">{t('dashboard.card.voices.title')}</h2>
          <p className="ds-action-card-desc">{t('dashboard.card.voices.desc')}</p>
          <div className="ds-action-card-footer">
            <span>{t('dashboard.card.voices.cta')}</span>
          </div>
        </Link>
      </div>
    </div>
  );
};
