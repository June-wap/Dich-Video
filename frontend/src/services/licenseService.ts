import { apiFetch } from './httpClient';

export type LicenseStatus =
  | 'ACTIVE'
  | 'UNLICENSED'
  | 'EXPIRED'
  | 'INVALID'
  | 'MACHINE_MISMATCH'
  | 'CLOCK_TAMPERED'
  | 'BLOCKED'
  | 'DEVICE_LIMIT_REACHED'
  | 'REVOKED'
  | 'LEASE_EXPIRED';

export type LicenseType = 'lifetime' | 'time_limited';

export interface LicenseStatusResponse {
  status: LicenseStatus;
  is_active: boolean;
  machine_id: string;
  customer_name?: string;
  license_type?: LicenseType;
  issued_at?: string;
  expires_at?: string;
  days_left?: number;
  time_left_str?: string;
  is_trial?: boolean;
  message: string;
  is_cloud_managed?: boolean;
  validation_until?: string;
  grace_period_active?: boolean;
}

export interface ActivateLicenseResponse {
  ok: boolean;
  status: LicenseStatusResponse;
}

export const licenseService = {
  async getStatus(signal?: AbortSignal): Promise<LicenseStatusResponse> {
    return apiFetch<LicenseStatusResponse>('/license/status', { signal });
  },

  async activate(licenseKey: string): Promise<ActivateLicenseResponse> {
    return apiFetch<ActivateLicenseResponse>('/license/activate', {
      method: 'POST',
      body: { license_key: licenseKey.trim() },
    });
  },

  async deactivate(): Promise<LicenseStatusResponse> {
    return apiFetch<LicenseStatusResponse>('/license/deactivate', {
      method: 'POST',
    });
  },

  async refresh(): Promise<LicenseStatusResponse> {
    return apiFetch<LicenseStatusResponse>('/license/refresh', {
      method: 'POST',
    });
  },
};
