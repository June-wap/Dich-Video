import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

vi.mock('../hooks', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../hooks')>();
  return {
    ...actual,
    useVoiceProfiles: () => ({ profiles: [], loading: false, error: null, reload: vi.fn() }),
  };
});

vi.mock('../services/voiceProfileService', () => ({
  voiceProfileService: { create: vi.fn(), synthesizeTest: vi.fn(), resolveAudioUrl: vi.fn() },
}));

import { VoiceCloningPage } from './VoiceCloningPage';
import { PRODUCTION_TTS_LANGUAGE_IDS } from '../config/productionLanguages';

describe('VoiceCloningPage language contract', () => {
  it('uses the complete shared production target-language list without exposing an engine', async () => {
    const user = userEvent.setup();
    render(<MemoryRouter><VoiceCloningPage /></MemoryRouter>);
    const selector = screen.getByLabelText('Ngôn ngữ đầu ra');
    const values = Array.from((selector as HTMLSelectElement).options).map((option) => option.value);
    expect(values).toEqual(PRODUCTION_TTS_LANGUAGE_IDS);
    expect(screen.getByRole('option', { name: 'Spanish' })).toHaveValue('es');
    expect(screen.getByRole('option', { name: 'Korean' })).toHaveValue('ko');
    expect(screen.getByRole('option', { name: 'French' })).toHaveValue('fr');
    expect(screen.getByRole('option', { name: 'Vietnamese (Tiếng Việt)' })).toHaveValue('vi');

    await user.selectOptions(selector, 'es');
    expect(selector).toHaveValue('es');
    await user.selectOptions(selector, 'ko');
    expect(selector).toHaveValue('ko');
    expect(screen.queryByLabelText(/provider|engine|model|runtime/i)).not.toBeInTheDocument();
  });
});
