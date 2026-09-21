import { afterEach, describe, expect, it, vi } from 'vitest';
import * as httpClient from './httpClient';
import { API_BASE_URL } from './httpClient';
import { voiceProfileService } from './voiceProfileService';
import type { VoiceProfile, CloneTTSResult } from './voiceProfileService';

const API_ORIGIN = new URL(API_BASE_URL).origin;

const PROFILE: VoiceProfile = {
  profile_id: 'p1',
  name: 'Giong Mau',
  provider: 'test-provider',
  status: 'ready',
  reference: { duration_seconds: 12.5, sample_rate: 24000, channels: 1 },
};

describe('voiceProfileService', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('create() POSTs multipart/form-data to /voices/profiles and unwraps { ok, data }', async () => {
    const apiFetchSpy = vi
      .spyOn(httpClient, 'apiFetch')
      .mockResolvedValueOnce({ ok: true, data: PROFILE });
    const file = new File(['fake-bytes'], 'ref.wav', { type: 'audio/wav' });

    const result = await voiceProfileService.create({
      file,
      referenceTranscript: 'xin chao',
      name: 'Giong Mau',
    });

    expect(result).toEqual(PROFILE);
    expect(apiFetchSpy).toHaveBeenCalledTimes(1);
    const [path, options] = apiFetchSpy.mock.calls[0];
    expect(path).toBe('/voices/profiles');
    // apiFetch's `options` parameter has a default value ({}), which makes
    // it optional in apiFetch's own type signature - so the recorded call's
    // second tuple element is typed `ApiFetchOptions | undefined` even
    // though voiceProfileService.create() always passes one. Narrow it with
    // a real runtime check (rather than a non-null assertion, which asserts
    // without proving anything) so the property accesses below are
    // genuinely strict-null-safe, not a silenced check.
    if (!options) {
      throw new Error('apiFetch was called without an options argument');
    }
    expect(options.method).toBe('POST');
    expect(options.body).toBeInstanceOf(FormData);
    const form = options.body as FormData;
    // FormData.append(name, blob, filename) is spec'd to construct a NEW
    // File wrapping the same bytes whenever a filename is given (which
    // voiceProfileService.create() always does) - so form.get('file') is
    // never the same object reference as the original `file`, even though
    // it's the same upload. That's correct, unavoidable FormData/File
    // semantics, not a bug to work around in production code - assert
    // semantic equivalence (name/type/size) instead of identity. (Content
    // bytes are deliberately not compared via `.text()`: this environment's
    // File/Blob implementation doesn't implement it - name/type/size is
    // already a real, meaningful semantic check without it.)
    const uploaded = form.get('file');
    expect(uploaded).toBeInstanceOf(File);
    const uploadedFile = uploaded as File;
    expect(uploadedFile.name).toBe(file.name);
    expect(uploadedFile.type).toBe(file.type);
    expect(uploadedFile.size).toBe(file.size);
    expect(form.get('reference_transcript')).toBe('xin chao');
    expect(form.get('name')).toBe('Giong Mau');
  });

  it('create() omits the `name` form field when not provided', async () => {
    const apiFetchSpy = vi
      .spyOn(httpClient, 'apiFetch')
      .mockResolvedValueOnce({ ok: true, data: PROFILE });
    const file = new File(['fake-bytes'], 'ref.wav', { type: 'audio/wav' });

    await voiceProfileService.create({ file, referenceTranscript: 'xin chao' });

    const [, options] = apiFetchSpy.mock.calls[0];
    if (!options) {
      throw new Error('apiFetch was called without an options argument');
    }
    const form = options.body as FormData;
    expect(form.has('name')).toBe(false);
  });

  it('list() GETs /voices/profiles and unwraps { ok, data }', async () => {
    const apiFetchSpy = vi
      .spyOn(httpClient, 'apiFetch')
      .mockResolvedValueOnce({ ok: true, data: [PROFILE] });

    const result = await voiceProfileService.list();

    expect(result).toEqual([PROFILE]);
    expect(apiFetchSpy).toHaveBeenCalledWith('/voices/profiles', { signal: undefined });
  });

  it('get() GETs /voices/profiles/{id} with the id URL-encoded', async () => {
    const apiFetchSpy = vi
      .spyOn(httpClient, 'apiFetch')
      .mockResolvedValueOnce({ ok: true, data: PROFILE });

    const result = await voiceProfileService.get('a/b');

    expect(result).toEqual(PROFILE);
    expect(apiFetchSpy).toHaveBeenCalledWith('/voices/profiles/a%2Fb', { signal: undefined });
  });

  it('remove() DELETEs /voices/profiles/{id}', async () => {
    const apiFetchSpy = vi.spyOn(httpClient, 'apiFetch').mockResolvedValueOnce(undefined);

    await voiceProfileService.remove('p1');

    expect(apiFetchSpy).toHaveBeenCalledWith('/voices/profiles/p1', { method: 'DELETE', signal: undefined });
  });

  it('synthesizeTest() POSTs to /voices/profiles/{id}/test with speed forced to 1.0 and unwraps { ok, data }', async () => {
    const cloneResult: CloneTTSResult = {
      generation_id: 'g1',
      profile_id: 'p1',
      status: 'completed',
      provider: 'test-provider',
      language: 'vi',
      duration_seconds: 3.2,
      sample_rate: 24000,
      channels: 1,
      format: 'wav',
      audio_url: '/api/audio/g1.wav',
    };
    const apiFetchSpy = vi
      .spyOn(httpClient, 'apiFetch')
      .mockResolvedValueOnce({ ok: true, data: cloneResult });

    const result = await voiceProfileService.synthesizeTest('p1', {
      text: 'xin chao ban',
      language: 'vi',
      format: 'wav',
    });

    expect(result).toEqual(cloneResult);
    expect(apiFetchSpy).toHaveBeenCalledWith('/voices/profiles/p1/test', {
      method: 'POST',
      body: { text: 'xin chao ban', language: 'vi', speed: 1.0, format: 'wav' },
      signal: undefined,
    });
  });

  it('resolveAudioUrl() qualifies a backend-relative audio_url', () => {
    const resolved = voiceProfileService.resolveAudioUrl({ audio_url: '/api/audio/g1.wav' });
    expect(resolved).toBe(`${API_ORIGIN}/api/audio/g1.wav`);
  });
});
