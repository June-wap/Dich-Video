/**
 * BYOK (Bring Your Own Key) Gemini translation settings. Mirrors
 * backend/api/settings.py and backend/schemas/settings.py field-for-field.
 * Direct typed JSON responses (no ok/data envelope) - same convention as
 * systemService's /system/status, not voiceProfileService's OkEnvelope<T>.
 *
 * This app never stores or ships a shared API key: the key saved here is
 * whatever the person running this install entered themselves, used only by
 * this install's own backend for this install's own translation requests.
 */
import { apiFetch } from './httpClient';

export interface TranslationSettingsStatus {
  configured: boolean;
  /** Masked preview (e.g. "AIza…9F") of the saved key, or null if unset.
   * Never the real key - the backend does not echo it back in full. */
  key_preview: string | null;
}

export const translationSettingsService = {
  /** GET /api/settings/translation */
  async get(signal?: AbortSignal): Promise<TranslationSettingsStatus> {
    return apiFetch<TranslationSettingsStatus>('/settings/translation', { signal });
  },

  /** POST /api/settings/translation - saves (or replaces) the key. */
  async save(geminiApiKey: string, signal?: AbortSignal): Promise<TranslationSettingsStatus> {
    return apiFetch<TranslationSettingsStatus>('/settings/translation', {
      method: 'POST',
      body: { gemini_api_key: geminiApiKey },
      signal,
    });
  },

  /** DELETE /api/settings/translation - clears the saved key. */
  async clear(signal?: AbortSignal): Promise<TranslationSettingsStatus> {
    return apiFetch<TranslationSettingsStatus>('/settings/translation', { method: 'DELETE', signal });
  },
};
