import { useCallback, useEffect, useRef, useState } from 'react';
import { voiceProfileService, type VoiceProfile } from '../services/voiceProfileService';
import { ApiError, NetworkError } from '../services/httpClient';

export interface UseVoiceProfilesError {
  code?: string;
  message: string;
}

export interface UseVoiceProfilesResult {
  profiles: VoiceProfile[];
  loading: boolean;
  error: UseVoiceProfilesError | null;
  /** Re-fetches GET /api/voices/profiles. Callers use this after creating a
   * new profile so both VoiceCloningPage's "load existing profile" list and
   * LongFormPage's voice picker stay in sync without duplicating the fetch
   * logic in either page. */
  reload: () => Promise<void>;
}

function describeError(err: unknown): UseVoiceProfilesError {
  if (err instanceof ApiError) return { code: err.code, message: err.message };
  if (err instanceof NetworkError) return { message: err.message };
  if (err instanceof Error) return { message: err.message };
  return { message: 'Đã xảy ra lỗi không xác định.' };
}

/**
 * Shared GET /api/voices/profiles loader (Task 4). Centralizes profile-list
 * fetching so it lives in one place rather than being re-implemented per
 * page - both VoiceCloningPage and LongFormPage need the same real,
 * server-persisted list of profiles.
 */
export function useVoiceProfiles(): UseVoiceProfilesResult {
  const [profiles, setProfiles] = useState<VoiceProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<UseVoiceProfilesError | null>(null);

  const mountedRef = useRef(true);
  const abortControllerRef = useRef<AbortController | null>(null);

  const reload = useCallback(async () => {
    abortControllerRef.current?.abort();
    const controller = new AbortController();
    abortControllerRef.current = controller;

    setLoading(true);
    setError(null);
    try {
      const list = await voiceProfileService.list(controller.signal);
      if (!mountedRef.current) return;
      setProfiles(list);
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return;
      if (!mountedRef.current) return;
      setError(describeError(err));
    } finally {
      if (mountedRef.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    void reload();
    return () => {
      mountedRef.current = false;
      abortControllerRef.current?.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { profiles, loading, error, reload };
}
