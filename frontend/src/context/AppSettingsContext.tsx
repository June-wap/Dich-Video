/**
 * Single source of truth for the General/Audio/Performance/Storage/Advanced
 * settings (backend/schemas/app_settings.py via appSettingsService), loaded
 * once at app startup and shared across the whole app - not just the
 * Settings page - so that:
 *  - Settings > General > Theme really re-skins every page (applies
 *    data-theme on <html>, including live "system" preference tracking).
 *  - Settings > General > Language really switches the app chrome via
 *    ../i18n's I18nProvider.
 *  - Other pages (TTSPage for Output Format, DiagnosticsPage for Debug
 *    Logging state, Sidebar for real status) can read the same settings
 *    without re-fetching them.
 *
 * SettingsPage itself still owns its own per-tab form state (so unsaved
 * edits don't leak elsewhere) and calls save() here only once a field is
 * actually persisted to the backend.
 */
import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { appSettingsService, type AppSettings, type AppSettingsResponse } from '../services/appSettingsService';
import { ApiError, NetworkError } from '../services/httpClient';
import { I18nProvider, type Locale } from '../i18n';

interface AppSettingsContextValue {
  settings: AppSettingsResponse | null;
  loading: boolean;
  error: string | null;
  reload: () => Promise<void>;
  save: (next: AppSettings) => Promise<AppSettingsResponse>;
}

const AppSettingsContext = createContext<AppSettingsContextValue | null>(null);

function applyTheme(theme: string) {
  const root = document.documentElement;
  if (theme === 'system') {
    const prefersDark = window.matchMedia?.('(prefers-color-scheme: dark)').matches;
    root.dataset.theme = prefersDark ? 'dark' : 'light';
  } else {
    root.dataset.theme = theme === 'dark' ? 'dark' : 'light';
  }
}

export const AppSettingsProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [settings, setSettings] = useState<AppSettingsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await appSettingsService.get();
      setSettings(data);
    } catch (err) {
      setError(
        err instanceof ApiError || err instanceof NetworkError
          ? err.message
          : 'Không thể tải cài đặt.'
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // Apply the theme to <html> whenever it changes, and keep "system" live.
  useEffect(() => {
    const theme = settings?.app_theme ?? 'light';
    applyTheme(theme);
    if (theme !== 'system' || !window.matchMedia) return;
    const media = window.matchMedia('(prefers-color-scheme: dark)');
    const handler = () => applyTheme('system');
    media.addEventListener?.('change', handler);
    return () => media.removeEventListener?.('change', handler);
  }, [settings?.app_theme]);

  const save = useCallback(async (next: AppSettings) => {
    const saved = await appSettingsService.save(next);
    setSettings(saved);
    return saved;
  }, []);

  const value = useMemo<AppSettingsContextValue>(
    () => ({ settings, loading, error, reload: load, save }),
    [settings, loading, error, load, save]
  );

  const locale: Locale = settings?.app_lang === 'en' ? 'en' : 'vi';

  return (
    <AppSettingsContext.Provider value={value}>
      <I18nProvider locale={locale}>{children}</I18nProvider>
    </AppSettingsContext.Provider>
  );
};

export function useAppSettings(): AppSettingsContextValue {
  const ctx = useContext(AppSettingsContext);
  if (!ctx) throw new Error('useAppSettings must be used within AppSettingsProvider');
  return ctx;
}
