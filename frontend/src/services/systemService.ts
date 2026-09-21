/**
 * Real hardware/runtime status for the Diagnostics page (Task 12) and the
 * Sidebar/Dashboard status displays. Mirrors backend/schemas/system.py
 * field-for-field. Direct typed JSON responses (no ok/data envelope) - same
 * convention as translationSettingsService/appSettingsService.
 */
import { apiFetch } from './httpClient';

export type ProviderState = 'NOT_LOADED' | 'LOADING' | 'READY' | 'UNLOADING' | 'ERROR' | 'UNAVAILABLE';

export interface SystemStatus {
  status: 'ready' | 'degraded';
  python_version: string;
  torch_version: string | null;
  cuda_available: boolean;
  gpu_name: string | null;
  primary_provider: string | null;
  provider_state: ProviderState | null;
  audio: { sample_rate: number; channels: number };
  runtime_mode: 'local';
}

export interface SystemLogsResponse {
  logs: string[];
}

export const systemService = {
  /** GET /api/system/status */
  async status(signal?: AbortSignal): Promise<SystemStatus> {
    return apiFetch<SystemStatus>('/system/status', { signal });
  },

  /** GET /api/system/logs - real, in-memory-only backend log lines. */
  async logs(signal?: AbortSignal): Promise<SystemLogsResponse> {
    return apiFetch<SystemLogsResponse>('/system/logs', { signal });
  },
};
