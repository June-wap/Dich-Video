import { describe, expect, it } from 'vitest';
import { PRODUCTION_TTS_LANGUAGE_IDS, PRODUCTION_TTS_LANGUAGES } from './productionLanguages';

describe('PRODUCTION_TTS_LANGUAGES', () => {
  it('is the complete canonical UI language contract for Short TTS and cloning', () => {
    expect(PRODUCTION_TTS_LANGUAGE_IDS).toEqual([
      'vi', 'ar', 'da', 'de', 'el', 'en', 'es', 'fi', 'fr', 'he', 'hi', 'it',
      'ja', 'ko', 'ms', 'nl', 'no', 'pl', 'pt', 'ru', 'sv', 'sw', 'tr', 'zh',
    ]);
    expect(PRODUCTION_TTS_LANGUAGES.find((item) => item.value === 'es')?.label).toBe('Spanish');
    expect(PRODUCTION_TTS_LANGUAGES.find((item) => item.value === 'ko')?.label).toBe('Korean');
    expect(PRODUCTION_TTS_LANGUAGES.find((item) => item.value === 'fr')?.label).toBe('French');
    expect(PRODUCTION_TTS_LANGUAGES.find((item) => item.value === 'vi')?.label).toBe('Vietnamese (Tiếng Việt)');
  });
});
