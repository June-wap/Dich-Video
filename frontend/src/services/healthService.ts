/** GET /api/health - used only for the real app version string (Sidebar
 * status panel used to hardcode "Prototype" regardless of the actual build).
 */
import { apiFetch } from './httpClient';

export interface HealthResponse {
  status: 'ok';
  service: string;
  version: string;
}

export const healthService = {
  async get(signal?: AbortSignal): Promise<HealthResponse> {
    return apiFetch<HealthResponse>('/health', { signal });
  },
};
