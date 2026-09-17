/**
 * Real API client for Voice Cloning profiles (Task 4). Mirrors backend
 * routes registered in backend/api/voices.py and their
 * backend/schemas/voices.py payloads field-for-field. `create()` is the only
 * multipart call in this codebase - see httpClient.ts's FormData handling.
 */
import { apiFetch, resolveBackendUrl } from './httpClient';

export interface ReferenceAudioInfo {
  duration_seconds: number;
  sample_rate: number;
  channels: number;
}

/** Matches backend VoiceProfileData exactly. Note there is no `language`
 * field - the backend does not tie a profile to the language its reference
 * audio was recorded in; synthesizeTest() picks the output language
 * independently, per call. */
export interface VoiceProfile {
  profile_id: string;
  name: string;
  provider: string;
  status: 'ready';
  reference?: ReferenceAudioInfo | null;
}

export type CloneAudioFormat = 'wav' | 'mp3';

/** Matches backend CloneTTSData exactly. */
export interface CloneTTSResult {
  generation_id: string;
  profile_id: string;
  status: 'completed';
  provider: string;
  language: string;
  duration_seconds: number;
  sample_rate: number;
  channels: number;
  format: CloneAudioFormat;
  audio_url: string;
}

export interface CreateVoiceProfilePayload {
  file: File;
  /** Exact transcript of what is spoken in `file` - required and validated
   * server-side (backend/services/voice_profile_service.py:
   * INVALID_REFERENCE_TRANSCRIPT if blank or >2000 chars). */
  referenceTranscript: string;
  /** Optional display name; the backend defaults to "Voice Profile
   * {id[:8]}" when omitted. */
  name?: string | null;
}

export interface SynthesizeCloneTestPayload {
  text: string;
  language: string;
  format: CloneAudioFormat;
}

interface OkEnvelope<T> {
  ok: true;
  data: T;
}

export const voiceProfileService = {
  /** POST /api/voices/profiles (multipart/form-data) -> created VoiceProfile
   * with real, server-measured reference.duration_seconds/sample_rate/
   * channels. Throws ApiError with codes such as INVALID_REFERENCE_AUDIO,
   * REFERENCE_AUDIO_TOO_LARGE (>15MB), or INVALID_REFERENCE_TRANSCRIPT for
   * validation failures - see backend/errors/__init__.py ErrorCode. */
  async create(payload: CreateVoiceProfilePayload, signal?: AbortSignal): Promise<VoiceProfile> {
    const form = new FormData();
    form.append('file', payload.file, payload.file.name);
    form.append('reference_transcript', payload.referenceTranscript);
    if (payload.name) form.append('name', payload.name);
    const response = await apiFetch<OkEnvelope<VoiceProfile>>('/voices/profiles', {
      method: 'POST',
      body: form,
      signal,
    });
    return response.data;
  },

  /** GET /api/voices/profiles -> every persisted profile. */
  async list(signal?: AbortSignal): Promise<VoiceProfile[]> {
    const response = await apiFetch<OkEnvelope<VoiceProfile[]>>('/voices/profiles', { signal });
    return response.data;
  },

  /** GET /api/voices/profiles/{id}. Throws ApiError(VOICE_PROFILE_NOT_FOUND)
   * for an unknown or malformed id. */
  async get(profileId: string, signal?: AbortSignal): Promise<VoiceProfile> {
    const response = await apiFetch<OkEnvelope<VoiceProfile>>(
      `/voices/profiles/${encodeURIComponent(profileId)}`,
      { signal }
    );
    return response.data;
  },

  /** DELETE /api/voices/profiles/{id}. Throws ApiError(PROFILE_IN_USE) if a
   * long-form job currently references it. */
  async remove(profileId: string, signal?: AbortSignal): Promise<void> {
    await apiFetch(`/voices/profiles/${encodeURIComponent(profileId)}`, { method: 'DELETE', signal });
  },

  /** POST /api/voices/profiles/{id}/test -> a SYNCHRONOUS, already-completed
   * CloneTTSResult (no job/poll cycle - this call resolves once audio is
   * ready, unlike ttsJobService/longFormJobService). `speed` is
   * deliberately not exposed as a parameter: the backend only accepts
   * exactly 1.0 (INVALID_SPEED otherwise), same restriction as Short TTS. */
  async synthesizeTest(
    profileId: string,
    payload: SynthesizeCloneTestPayload,
    signal?: AbortSignal
  ): Promise<CloneTTSResult> {
    const response = await apiFetch<OkEnvelope<CloneTTSResult>>(
      `/voices/profiles/${encodeURIComponent(profileId)}/test`,
      {
        method: 'POST',
        body: { text: payload.text, language: payload.language, speed: 1.0, format: payload.format },
        signal,
      }
    );
    return response.data;
  },

  /** Turn a CloneTTSResult's backend-relative audio_url into a fetchable
   * absolute URL. Never reconstructs the artifact id/path itself. */
  resolveAudioUrl(result: Pick<CloneTTSResult, 'audio_url'>): string {
    return resolveBackendUrl(result.audio_url);
  },
};
