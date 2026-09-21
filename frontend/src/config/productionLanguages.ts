/**
 * Canonical Short-TTS and Voice Cloning target-language contract.
 * `vi` is routed by the backend to VieNeu; every other ID is routed to
 * Chatterbox Multilingual V3. Pages must select only the language, never a
 * provider or engine.
 */
export const PRODUCTION_TTS_LANGUAGES: { value: string; label: string }[] = [
  { value: 'vi', label: 'Vietnamese (Tiếng Việt)' },
  { value: 'ar', label: 'Arabic' },
  { value: 'da', label: 'Danish' },
  { value: 'de', label: 'German' },
  { value: 'el', label: 'Greek' },
  { value: 'en', label: 'English (Tiếng Anh)' },
  { value: 'es', label: 'Spanish' },
  { value: 'fi', label: 'Finnish' },
  { value: 'fr', label: 'French' },
  { value: 'he', label: 'Hebrew' },
  { value: 'hi', label: 'Hindi' },
  { value: 'it', label: 'Italian' },
  { value: 'ja', label: 'Japanese (Tiếng Nhật)' },
  { value: 'ko', label: 'Korean' },
  { value: 'ms', label: 'Malay' },
  { value: 'nl', label: 'Dutch' },
  { value: 'no', label: 'Norwegian' },
  { value: 'pl', label: 'Polish' },
  { value: 'pt', label: 'Portuguese' },
  { value: 'ru', label: 'Russian' },
  { value: 'sv', label: 'Swedish' },
  { value: 'sw', label: 'Swahili' },
  { value: 'tr', label: 'Turkish' },
  { value: 'zh', label: 'Chinese (Tiếng Trung)' },
];

export const PRODUCTION_TTS_LANGUAGE_IDS = PRODUCTION_TTS_LANGUAGES.map(({ value }) => value);
