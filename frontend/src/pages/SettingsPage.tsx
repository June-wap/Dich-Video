import React, { useEffect, useState } from 'react';
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
  Button,
  Input,
  Select,
  StatusBadge,
  ErrorState,
} from '../components';
import { useDeveloperMode } from '../hooks';
import { useAppSettings } from '../context/AppSettingsContext';
import { useT } from '../i18n';
import { translationSettingsService } from '../services/translationSettingsService';
import { healthService } from '../services/healthService';
import { ApiError } from '../services/httpClient';
import type { AppSettings } from '../services/appSettingsService';
import {
  getNotificationPermission,
  requestNotificationPermission,
  type NotificationPermissionState,
} from '../utils/notifications';

type SettingsTab = 'general' | 'audio' | 'performance' | 'storage' | 'advanced' | 'translation';

function formatBytes(bytes: number): string {
  if (bytes <= 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const exponent = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const value = bytes / Math.pow(1024, exponent);
  return `${exponent === 0 ? value : value.toFixed(1)} ${units[exponent]}`;
}

export const SettingsPage: React.FC = () => {
  const { t } = useT();
  const { settings, loading, error, reload, save } = useAppSettings();
  const [activeTab, setActiveTab] = useState<SettingsTab>('general');
  const [form, setForm] = useState<AppSettings | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [version, setVersion] = useState<string | null>(null);
  const [updateStatus, setUpdateStatus] = useState<string | null>(null);
  const [permission, setPermission] = useState<NotificationPermissionState>('default');

  // Sync local editable form from the shared context whenever it (re)loads
  // or a save completes - never fight the user mid-edit, since the only
  // thing that changes `settings` after the initial load is this page's own
  // save() call, which always reflects exactly what was just submitted.
  useEffect(() => {
    if (settings) {
      const { actual_db_path, actual_output_dir, output_dir_bytes, ...editable } = settings;
      setForm(editable);
    }
  }, [settings]);

  useEffect(() => {
    healthService.get().then((data) => setVersion(data.version)).catch(() => {});
    setPermission(getNotificationPermission());
  }, []);

  // Translation (Gemini BYOK) settings state - unaffected by this rewrite,
  // still the same real GET/POST/DELETE /api/settings/translation flow.
  const [geminiKeyInput, setGeminiKeyInput] = useState('');
  const [geminiConfigured, setGeminiConfigured] = useState(false);
  const [geminiKeyPreview, setGeminiKeyPreview] = useState<string | null>(null);
  const [geminiLoading, setGeminiLoading] = useState(true);
  const [geminiSaving, setGeminiSaving] = useState(false);
  const [geminiError, setGeminiError] = useState<string | null>(null);
  const [geminiSaved, setGeminiSaved] = useState(false);

  useEffect(() => {
    let cancelled = false;
    translationSettingsService
      .get()
      .then((status) => {
        if (cancelled) return;
        setGeminiConfigured(status.configured);
        setGeminiKeyPreview(status.key_preview);
      })
      .catch((err) => {
        if (cancelled) return;
        setGeminiError(err instanceof Error ? err.message : 'Không thể tải trạng thái cấu hình.');
      })
      .finally(() => {
        if (!cancelled) setGeminiLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const handleSaveGeminiKey = async () => {
    if (!geminiKeyInput.trim()) return;
    setGeminiSaving(true);
    setGeminiError(null);
    try {
      const status = await translationSettingsService.save(geminiKeyInput.trim());
      setGeminiConfigured(status.configured);
      setGeminiKeyPreview(status.key_preview);
      setGeminiKeyInput('');
      setGeminiSaved(true);
      setTimeout(() => setGeminiSaved(false), 2500);
    } catch (err) {
      setGeminiError(
        err instanceof ApiError ? err.message : 'Không thể lưu API key. Kiểm tra kết nối tới backend cục bộ.'
      );
    } finally {
      setGeminiSaving(false);
    }
  };

  const handleClearGeminiKey = async () => {
    setGeminiSaving(true);
    setGeminiError(null);
    try {
      const status = await translationSettingsService.clear();
      setGeminiConfigured(status.configured);
      setGeminiKeyPreview(status.key_preview);
    } catch (err) {
      setGeminiError(err instanceof ApiError ? err.message : 'Không thể xoá API key.');
    } finally {
      setGeminiSaving(false);
    }
  };

  // --- General/Audio/Performance/Storage/Advanced: one real save handler,
  // shared by both the header "Lưu thay đổi" button and the Advanced tab's
  // own footer button - both persist the exact same full settings object.
  const patch = (partial: Partial<AppSettings>) => setForm((prev) => (prev ? { ...prev, ...partial } : prev));

  // "Quality preset" only has a real effect through num_steps (the diffusion
  // step count already fully wired end-to-end into TTSService/LongFormTTSService
  // - see backend/services/tts_service.py). Rather than persist quality_preset
  // as a second, disconnected knob, picking a preset here also sets the real
  // num_steps value, so this control genuinely changes synthesis output instead
  // of just being remembered and ignored. Dev Mode's Advanced tab exposes the
  // same num_steps field directly for users who want to fine-tune past the
  // three preset buckets - the two controls share one real setting underneath.
  const QUALITY_PRESET_STEPS: Record<string, number> = { fast: 8, balanced: 16, high: 32 };
  const handleQualityPresetChange = (preset: string) => {
    setForm((prev) => (prev ? { ...prev, quality_preset: preset, num_steps: QUALITY_PRESET_STEPS[preset] ?? prev.num_steps } : prev));
  };

  const handleSave = async () => {
    if (!form) return;
    setSaving(true);
    setSaveError(null);
    try {
      await save(form);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 2500);
    } catch (err) {
      setSaveError(
        err instanceof ApiError ? err.message : t('settings.saveFailed')
      );
    } finally {
      setSaving(false);
    }
  };

  const handleRequestNotificationPermission = async () => {
    const result = await requestNotificationPermission();
    setPermission(result);
  };

  const handleCheckUpdate = () => {
    // Honest: this build has no configured update manifest/channel to check
    // against, so this reports that plainly instead of a fake "you're up to
    // date" message like before.
    setUpdateStatus(t('settings.general.update.notConfigured'));
  };

  const { isDevMode, setDevMode } = useDeveloperMode();

  if (loading && !form) {
    return (
      <div style={{ padding: '40px', textAlign: 'center', color: 'var(--neutral-500)', fontSize: '13px' }}>
        {t('settings.loading')}
      </div>
    );
  }

  if (error && !form) {
    return <ErrorState title={t('settings.loadFailed')} message={error} retryLabel={t('settings.retry')} onRetry={reload} />;
  }

  if (!form || !settings) return null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Top Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h1 style={{ fontSize: '20px', fontWeight: 700, color: 'var(--neutral-900)' }}>
            {t('settings.header.title')}
          </h1>
          <p style={{ fontSize: '13px', color: 'var(--neutral-500)', marginTop: '2px' }}>
            {t('settings.header.subtitle')}
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {saveSuccess && <StatusBadge status="success" label={t('settings.saved')} size="sm" />}
          <Button variant="primary" size="md" isLoading={saving} onClick={handleSave}>
            {t('settings.save')}
          </Button>
        </div>
      </div>

      {saveError && (
        <ErrorState title={t('settings.saveFailed')} message={saveError} retryLabel={t('settings.retry')} onRetry={handleSave} />
      )}

      {/* Main Settings Layout: Left Nav + Right Panel */}
      <div className="ds-settings-layout">
        {/* Left Navigation */}
        <nav className="ds-settings-nav">
          <button type="button" className={`ds-settings-nav-btn ${activeTab === 'general' ? 'ds-settings-nav-btn--active' : ''}`} onClick={() => setActiveTab('general')}>
            <span>{t('settings.tab.general')}</span>
          </button>
          <button type="button" className={`ds-settings-nav-btn ${activeTab === 'audio' ? 'ds-settings-nav-btn--active' : ''}`} onClick={() => setActiveTab('audio')}>
            <span>{t('settings.tab.audio')}</span>
          </button>
          <button type="button" className={`ds-settings-nav-btn ${activeTab === 'performance' ? 'ds-settings-nav-btn--active' : ''}`} onClick={() => setActiveTab('performance')}>
            <span>{t('settings.tab.performance')}</span>
          </button>
          <button type="button" className={`ds-settings-nav-btn ${activeTab === 'storage' ? 'ds-settings-nav-btn--active' : ''}`} onClick={() => setActiveTab('storage')}>
            <span>{t('settings.tab.storage')}</span>
          </button>
          <button type="button" className={`ds-settings-nav-btn ${activeTab === 'advanced' ? 'ds-settings-nav-btn--active' : ''}`} onClick={() => setActiveTab('advanced')}>
            <span>{t('settings.tab.advanced')}</span>
          </button>
          <button type="button" className={`ds-settings-nav-btn ${activeTab === 'translation' ? 'ds-settings-nav-btn--active' : ''}`} onClick={() => setActiveTab('translation')}>
            <span>{t('settings.tab.translation')}</span>
          </button>
        </nav>

        {/* Right Content Panel */}
        <div className="ds-settings-content">
          {/* ============================= GENERAL ============================= */}
          {activeTab === 'general' && (
            <Card>
              <CardHeader>
                <CardTitle>{t('settings.general.title')}</CardTitle>
                <CardDescription>{t('settings.general.desc')}</CardDescription>
              </CardHeader>

              <CardContent style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                <Select
                  label={t('settings.general.language.label')}
                  options={[
                    { value: 'vi', label: t('settings.general.language.vi') },
                    { value: 'en', label: t('settings.general.language.en') },
                  ]}
                  value={form.app_lang}
                  onChange={(e) => patch({ app_lang: e.target.value })}
                  hint={t('settings.general.language.hint')}
                />

                <Select
                  label={t('settings.general.theme.label')}
                  options={[
                    { value: 'light', label: t('settings.general.theme.light') },
                    { value: 'dark', label: t('settings.general.theme.dark') },
                    { value: 'system', label: t('settings.general.theme.system') },
                  ]}
                  value={form.app_theme}
                  onChange={(e) => patch({ app_theme: e.target.value })}
                  hint={t('settings.general.theme.hint')}
                />

                <div style={{ display: 'flex', flexDirection: 'column', borderTop: '1px solid var(--border-subtle)', paddingTop: '16px', gap: '8px' }}>
                  <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--neutral-900)' }}>
                    {t('settings.general.notifications.title')}
                  </span>

                  <div className="ds-toggle-row">
                    <div>
                      <strong style={{ fontSize: '13px', color: 'var(--neutral-800)', display: 'block' }}>
                        {t('settings.general.notify.completion.title')}
                      </strong>
                      <span style={{ fontSize: '12px', color: 'var(--neutral-500)' }}>
                        {t('settings.general.notify.completion.desc')}
                      </span>
                    </div>
                    <label className="ds-switch">
                      <input type="checkbox" checked={form.notify_completion} onChange={(e) => patch({ notify_completion: e.target.checked })} />
                      <span className="ds-switch-slider" />
                    </label>
                  </div>

                  <div className="ds-toggle-row">
                    <div>
                      <strong style={{ fontSize: '13px', color: 'var(--neutral-800)', display: 'block' }}>
                        {t('settings.general.notify.errors.title')}
                      </strong>
                      <span style={{ fontSize: '12px', color: 'var(--neutral-500)' }}>
                        {t('settings.general.notify.errors.desc')}
                      </span>
                    </div>
                    <label className="ds-switch">
                      <input type="checkbox" checked={form.notify_errors} onChange={(e) => patch({ notify_errors: e.target.checked })} />
                      <span className="ds-switch-slider" />
                    </label>
                  </div>

                  {(form.notify_completion || form.notify_errors) && permission !== 'granted' && permission !== 'unsupported' && (
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px', padding: '10px 14px', background: 'var(--warning-bg)', border: '1px solid var(--warning-border)', borderRadius: 'var(--radius-md)' }}>
                      <span style={{ fontSize: '12px', color: 'var(--warning-text)' }}>
                        {t('settings.general.notify.permission.denied')}
                      </span>
                      {permission === 'default' && (
                        <Button size="sm" variant="outline" onClick={handleRequestNotificationPermission}>
                          {t('settings.general.notify.permission.request')}
                        </Button>
                      )}
                    </div>
                  )}
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', borderTop: '1px solid var(--border-subtle)', paddingTop: '16px', gap: '8px' }}>
                  <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--neutral-900)' }}>
                    {t('settings.general.update.title')}
                  </span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <Button variant="outline" size="sm" onClick={handleCheckUpdate}>
                      {t('settings.general.update.check')}
                    </Button>
                    <span style={{ fontSize: '12px', color: 'var(--neutral-500)' }}>
                      {t('settings.general.update.current')}: <strong>{version ? `v${version}` : '—'}</strong>
                    </span>
                  </div>
                  {updateStatus && (
                    <span style={{ fontSize: '12px', color: 'var(--neutral-600)' }}>{updateStatus}</span>
                  )}
                </div>
              </CardContent>
            </Card>
          )}

          {/* ============================== AUDIO =============================== */}
          {activeTab === 'audio' && (
            <Card>
              <CardHeader>
                <CardTitle>{t('settings.audio.title')}</CardTitle>
                <CardDescription>{t('settings.audio.desc')}</CardDescription>
              </CardHeader>

              <CardContent style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                <Select
                  label={t('settings.audio.format.label')}
                  options={[
                    { value: 'wav', label: t('settings.audio.format.wav') },
                    { value: 'mp3', label: t('settings.audio.format.mp3') },
                    { value: 'wav+mp3', label: t('settings.audio.format.both') },
                  ]}
                  value={form.output_format}
                  onChange={(e) => patch({ output_format: e.target.value })}
                  hint={t('settings.audio.format.hint')}
                />

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '16px' }}>
                  <div style={{ padding: '12px', background: 'var(--neutral-50)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-default)' }}>
                    <span style={{ fontSize: '11px', color: 'var(--neutral-500)', textTransform: 'uppercase' }}>{t('settings.audio.sampleRate.label')}</span>
                    <p style={{ fontSize: '15px', fontWeight: 600, color: 'var(--neutral-900)', marginTop: '2px' }}>
                      24,000 Hz
                    </p>
                    <span style={{ fontSize: '11px', color: 'var(--neutral-500)' }}>{t('settings.audio.sampleRate.hint')}</span>
                  </div>

                  <div style={{ padding: '12px', background: 'var(--neutral-50)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-default)' }}>
                    <span style={{ fontSize: '11px', color: 'var(--neutral-500)', textTransform: 'uppercase' }}>{t('settings.audio.channels.label')}</span>
                    <p style={{ fontSize: '15px', fontWeight: 600, color: 'var(--neutral-900)', marginTop: '2px' }}>
                      Mono (1)
                    </p>
                    <span style={{ fontSize: '11px', color: 'var(--neutral-500)' }}>{t('settings.audio.channels.hint')}</span>
                  </div>
                </div>

                <Select
                  label={t('settings.audio.pause.label')}
                  options={[
                    { value: '250', label: '250 ms' },
                    { value: '400', label: '400 ms' },
                    { value: '600', label: '600 ms' },
                  ]}
                  value={String(form.pause_policy_ms)}
                  onChange={(e) => patch({ pause_policy_ms: Number(e.target.value) })}
                  hint={t('settings.audio.pause.hint')}
                />

                <div className="ds-toggle-row">
                  <div>
                    <strong style={{ fontSize: '13px', color: 'var(--neutral-800)', display: 'block' }}>
                      {t('settings.audio.silenceTrim.title')}
                    </strong>
                    <span style={{ fontSize: '12px', color: 'var(--neutral-500)' }}>{t('settings.audio.silenceTrim.desc')}</span>
                  </div>
                  <label className="ds-switch">
                    <input type="checkbox" checked={form.silence_trim} onChange={(e) => patch({ silence_trim: e.target.checked })} />
                    <span className="ds-switch-slider" />
                  </label>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <Input
                    label={t('settings.audio.outputDir.label')}
                    value={form.output_dir ?? settings.actual_output_dir}
                    onChange={(e) => patch({ output_dir: e.target.value })}
                    hint={t('settings.audio.outputDir.hint')}
                  />
                  <div style={{ display: 'flex', gap: '8px' }}>
                    <Button size="sm" variant="ghost" onClick={() => patch({ output_dir: null })}>
                      {t('settings.audio.outputDir.reset')}
                    </Button>
                  </div>
                  <span style={{ fontSize: '11px', color: 'var(--neutral-500)' }}>{t('settings.audio.outputDir.browseUnavailable')}</span>
                </div>
              </CardContent>
            </Card>
          )}

          {/* ============================ PERFORMANCE ============================ */}
          {activeTab === 'performance' && (
            <Card>
              <CardHeader>
                <CardTitle>{t('settings.performance.title')}</CardTitle>
                <CardDescription>{t('settings.performance.desc')}</CardDescription>
              </CardHeader>

              <CardContent style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <label className="ds-label">{t('settings.performance.device.label')}</label>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '12px' }}>
                    <button
                      type="button"
                      onClick={() => patch({ device: 'gpu' })}
                      style={{
                        padding: '12px 16px',
                        border: `2px solid ${form.device === 'gpu' ? 'var(--color-primary-600)' : 'var(--border-default)'}`,
                        backgroundColor: form.device === 'gpu' ? 'var(--color-primary-50)' : 'var(--surface-white)',
                        borderRadius: 'var(--radius-md)', cursor: 'pointer', textAlign: 'left',
                        display: 'flex', flexDirection: 'column', gap: '4px',
                      }}
                    >
                      <strong style={{ fontSize: '14px', color: 'var(--neutral-900)' }}>{t('settings.performance.device.gpu.title')}</strong>
                      <span style={{ fontSize: '12px', color: 'var(--neutral-600)' }}>{t('settings.performance.device.gpu.desc')}</span>
                    </button>

                    <button
                      type="button"
                      onClick={() => patch({ device: 'cpu' })}
                      style={{
                        padding: '12px 16px',
                        border: `2px solid ${form.device === 'cpu' ? 'var(--color-primary-600)' : 'var(--border-default)'}`,
                        backgroundColor: form.device === 'cpu' ? 'var(--color-primary-50)' : 'var(--surface-white)',
                        borderRadius: 'var(--radius-md)', cursor: 'pointer', textAlign: 'left',
                        display: 'flex', flexDirection: 'column', gap: '4px',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                        <strong style={{ fontSize: '14px', color: 'var(--neutral-900)' }}>{t('settings.performance.device.cpu.title')}</strong>
                        <StatusBadge status="warning" label="Experimental" size="sm" />
                      </div>
                      <span style={{ fontSize: '12px', color: 'var(--neutral-500)' }}>{t('settings.performance.device.cpu.desc')}</span>
                    </button>
                  </div>
                  <span style={{ fontSize: '11px', color: 'var(--neutral-500)' }}>{t('settings.performance.device.restartNote')}</span>
                </div>

                <Select
                  label={t('settings.performance.quality.label')}
                  options={[
                    { value: 'fast', label: t('settings.performance.quality.fast') },
                    { value: 'balanced', label: t('settings.performance.quality.balanced') },
                    { value: 'high', label: t('settings.performance.quality.high') },
                  ]}
                  value={form.quality_preset}
                  onChange={(e) => handleQualityPresetChange(e.target.value)}
                  hint={t('settings.performance.quality.hint')}
                />

                <Select
                  label={t('settings.performance.retry.label')}
                  options={[
                    { value: '1', label: t('settings.performance.retry.1') },
                    { value: '2', label: t('settings.performance.retry.2') },
                    { value: '3', label: t('settings.performance.retry.3') },
                  ]}
                  value={String(form.retry_count)}
                  onChange={(e) => patch({ retry_count: Number(e.target.value) })}
                  hint={t('settings.performance.retry.hint')}
                />
              </CardContent>
            </Card>
          )}

          {/* ============================== STORAGE =============================== */}
          {activeTab === 'storage' && (
            <Card>
              <CardHeader>
                <CardTitle>{t('settings.storage.title')}</CardTitle>
                <CardDescription>{t('settings.storage.desc')}</CardDescription>
              </CardHeader>

              <CardContent style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                <Input
                  label={t('settings.storage.dbPath.label')}
                  value={settings.actual_db_path}
                  disabled
                  hint={t('settings.storage.dbPath.hint')}
                />

                {/* Honest: unlike the DB path and output dir, the backend does not
                    expose a model-checkpoint directory as a runtime setting (it's
                    resolved internally by the provider at load time), so this no
                    longer shows a fabricated path - matches the same "don't invent
                    data the backend can't back up" rule used for Clear Cache and
                    the Diagnostics VRAM gauges elsewhere in this pass. */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  <span className="ds-label">{t('settings.storage.modelDir.label')}</span>
                  <span style={{ fontSize: '12px', color: 'var(--neutral-500)' }}>
                    {t('settings.storage.modelDir.hint')}
                  </span>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', padding: '14px 16px', background: 'var(--neutral-50)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-default)' }}>
                  <strong style={{ fontSize: '13px', color: 'var(--neutral-900)' }}>{t('settings.storage.usage.title')}</strong>
                  <span style={{ fontSize: '20px', fontWeight: 700, color: 'var(--neutral-900)', fontFamily: 'var(--font-family-mono)' }}>
                    {formatBytes(settings.output_dir_bytes)}
                  </span>
                  <span style={{ fontSize: '12px', color: 'var(--neutral-500)' }}>{t('settings.storage.usage.desc')}</span>
                  <span style={{ fontSize: '11px', color: 'var(--neutral-500)', marginTop: '4px' }}>{t('settings.storage.usage.note')}</span>
                </div>
              </CardContent>
            </Card>
          )}

          {/* ============================== ADVANCED =============================== */}
          {activeTab === 'advanced' && (
            <Card>
              <CardHeader>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <CardTitle>{t('settings.advanced.title')}</CardTitle>
                  <StatusBadge status="warning" label={t('settings.advanced.badge')} size="sm" />
                </div>
                <CardDescription>{t('settings.advanced.desc')}</CardDescription>
              </CardHeader>

              <CardContent style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <div className="ds-toggle-row">
                  <div>
                    <strong style={{ fontSize: '13px', color: 'var(--neutral-800)', display: 'block' }}>
                      {t('settings.advanced.devMode.title')}
                    </strong>
                    <span style={{ fontSize: '12px', color: 'var(--neutral-500)' }}>{t('settings.advanced.devMode.desc')}</span>
                  </div>
                  <label className="ds-switch">
                    <input type="checkbox" checked={isDevMode} onChange={(e) => setDevMode(e.target.checked)} />
                    <span className="ds-switch-slider" />
                  </label>
                </div>

                {isDevMode ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', padding: '16px', background: 'var(--neutral-50)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-default)' }}>
                    <Select
                      label={t('settings.advanced.numSteps.label')}
                      options={[
                        { value: '8', label: t('settings.advanced.numSteps.8') },
                        { value: '16', label: t('settings.advanced.numSteps.16') },
                        { value: '32', label: t('settings.advanced.numSteps.32') },
                      ]}
                      value={String(form.num_steps)}
                      onChange={(e) => patch({ num_steps: Number(e.target.value) })}
                      hint={t('settings.advanced.numSteps.hint')}
                    />

                    <div className="ds-toggle-row">
                      <div>
                        <strong style={{ fontSize: '13px', color: 'var(--neutral-800)', display: 'block' }}>
                          {t('settings.advanced.debugLogs.title')}
                        </strong>
                        <span style={{ fontSize: '12px', color: 'var(--neutral-500)' }}>{t('settings.advanced.debugLogs.desc')}</span>
                      </div>
                      <label className="ds-switch">
                        <input type="checkbox" checked={form.debug_logs} onChange={(e) => patch({ debug_logs: e.target.checked })} />
                        <span className="ds-switch-slider" />
                      </label>
                    </div>
                  </div>
                ) : (
                  <div style={{ padding: '16px', textAlign: 'center', background: 'var(--neutral-50)', borderRadius: 'var(--radius-md)', border: '1px dashed var(--border-strong)', color: 'var(--neutral-500)', fontSize: '13px' }}>
                    {t('settings.advanced.collapsed')}
                  </div>
                )}
              </CardContent>

              <CardFooter style={{ justifyContent: 'flex-end' }}>
                <Button variant="primary" size="md" isLoading={saving} onClick={handleSave}>
                  {t('settings.advanced.saveAdvanced')}
                </Button>
              </CardFooter>
            </Card>
          )}

          {/* ======================= TRANSLATION (Gemini BYOK) ======================= */}
          {activeTab === 'translation' && (
            <Card>
              <CardHeader>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <CardTitle>{t('settings.translation.title')}</CardTitle>
                  <StatusBadge
                    status={geminiConfigured ? 'success' : 'neutral'}
                    label={geminiConfigured ? t('settings.translation.configured') : t('settings.translation.notConfigured')}
                    size="sm"
                  />
                </div>
                <CardDescription>
                  Bắt buộc để tạo giọng nói cho ngôn ngữ khác tiếng Việt - văn bản được dịch sang ngôn ngữ đã
                  chọn trước khi đọc thành tiếng. Tiếng Việt không cần bước này.
                </CardDescription>
              </CardHeader>

              <CardContent style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                <div
                  style={{
                    padding: '12px 14px',
                    background: 'var(--neutral-50)',
                    borderRadius: 'var(--radius-md)',
                    border: '1px solid var(--border-default)',
                    fontSize: '12.5px',
                    color: 'var(--neutral-600)',
                    lineHeight: 1.6,
                  }}
                >
                  <strong style={{ color: 'var(--neutral-800)' }}>Đây là API key của riêng bạn (BYOK)</strong> -
                  ứng dụng này không đi kèm hay chia sẻ bất kỳ key nào. Tạo key miễn phí tại{' '}
                  <a href="https://aistudio.google.com/apikey" target="_blank" rel="noreferrer">
                    Google AI Studio
                  </a>{' '}
                  (không cần thẻ tín dụng). Lưu ý: ở gói miễn phí, Google có thể dùng nội dung bạn gửi để cải
                  thiện model của họ - văn bản sẽ được gửi qua mạng tới Gemini, không còn hoàn toàn offline cho
                  riêng bước dịch này.
                </div>

                {geminiLoading ? (
                  <div style={{ padding: '16px', textAlign: 'center', fontSize: '13px', color: 'var(--neutral-500)' }}>
                    Đang tải trạng thái cấu hình...
                  </div>
                ) : (
                  <>
                    {geminiConfigured && (
                      <div
                        style={{
                          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                          padding: '12px 14px', background: 'var(--success-bg, var(--neutral-50))',
                          borderRadius: 'var(--radius-md)', border: '1px solid var(--border-default)',
                        }}
                      >
                        <span style={{ fontSize: '13px', color: 'var(--neutral-800)' }}>
                          API key hiện tại: <code style={{ fontFamily: 'var(--font-family-mono)' }}>{geminiKeyPreview}</code>
                        </span>
                        <Button size="sm" variant="outline" isLoading={geminiSaving} onClick={handleClearGeminiKey}>
                          Xoá key
                        </Button>
                      </div>
                    )}

                    <Input
                      label={geminiConfigured ? 'Thay bằng API key khác' : 'Gemini API key'}
                      type="password"
                      value={geminiKeyInput}
                      onChange={(e) => setGeminiKeyInput(e.target.value)}
                      placeholder="AIza..."
                      hint="Dán API key lấy từ Google AI Studio. Key được lưu cục bộ trên máy này, không gửi đi đâu khác ngoài trực tiếp tới Gemini khi dịch."
                    />

                    {geminiError && (
                      <ErrorState
                        title="Không thể lưu cấu hình"
                        message={geminiError}
                        retryLabel="Thử lại"
                        onRetry={handleSaveGeminiKey}
                      />
                    )}
                  </>
                )}
              </CardContent>

              <CardFooter style={{ justifyContent: 'space-between' }}>
                {geminiSaved && <StatusBadge status="success" label="Đã lưu API key" size="sm" />}
                <Button
                  variant="primary"
                  size="md"
                  isLoading={geminiSaving}
                  disabled={!geminiKeyInput.trim()}
                  onClick={handleSaveGeminiKey}
                  style={{ marginLeft: 'auto' }}
                >
                  Lưu API key
                </Button>
              </CardFooter>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
};
