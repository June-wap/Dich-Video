/**
 * General app settings (General/Audio/Performance/Storage/Advanced tabs).
 * Mirrors backend/api/app_settings.py and backend/schemas/app_settings.py
 * field-for-field. Separate from translationSettingsService (Gemini BYOK key
 * has its own security handling) - same direct-JSON convention, no
 * ok/data envelope.
 */
import { apiFetch } from './httpClient';

export interface AppSettings {
  app_lang: string;
  app_theme: string;
  notify_completion: boolean;
  notify_errors: boolean;
  output_format: string;
  pause_policy_ms: number;
  silence_trim: boolean;
  output_dir: string | null;
  // "cpu" is experimental/unverified for OmniVoice output quality and only
  // takes effect on the next backend startup - see backend/schemas/
  // app_settings.py's own docstring on this field, and SettingsPage.tsx's
  // Performance > Device control, which reads/writes it.
  device: 'gpu' | 'cpu';
  quality_preset: string;
  retry_count: number;
  num_steps: number;
  debug_logs: boolean;
}

export interface AppSettingsResponse extends AppSettings {
  /** Real, server-computed values - read-only, never sent back on save. */
  actual_db_path: string;
  actual_output_dir: string;
  /** Real total size (bytes) of every file in actual_output_dir. */
  output_dir_bytes: number;
}

export const appSettingsService = {
  /** GET /api/settings/app */
  async get(signal?: AbortSignal): Promise<AppSettingsResponse> {
    return apiFetch<AppSettingsResponse>('/settings/app', { signal });
  },

  /** POST /api/settings/app - saves the full settings payload. */
  async save(settings: AppSettings, signal?: AbortSignal): Promise<AppSettingsResponse> {
    return apiFetch<AppSettingsResponse>('/settings/app', {
      method: 'POST',
      body: settings,
      signal,
    });
  },
};
