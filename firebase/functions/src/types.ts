export type LicenseStatus = 'active' | 'blocked' | 'expired';
export type LicensePlan = 'lifetime' | 'time_limited';
export type ActivationStatus = 'active' | 'revoked';

export type AuditEventType =
  | 'LICENSE_CREATED'
  | 'LICENSE_ACTIVATED'
  | 'LICENSE_REACTIVATED'
  | 'LICENSE_VALIDATED'
  | 'LICENSE_DEACTIVATED'
  | 'LICENSE_REVOKED'
  | 'LICENSE_BLOCKED'
  | 'LICENSE_UNBLOCKED'
  | 'LICENSE_EXTENDED'
  | 'DEVICE_LIMIT_EXCEEDED';

export interface LicenseDoc {
  status: LicenseStatus;
  plan: LicensePlan;
  maxDevices: number;
  activationCount: number;
  customerId: string;
  createdAt: FirebaseFirestore.Timestamp | FirebaseFirestore.FieldValue;
  expiresAt: FirebaseFirestore.Timestamp | null;
  metadata: {
    product: string;
    version: number;
    notes?: string;
  };
}

export interface DeviceDoc {
  machineIdHash: string;
  firstSeenAt: FirebaseFirestore.Timestamp | FirebaseFirestore.FieldValue;
  lastSeenAt: FirebaseFirestore.Timestamp | FirebaseFirestore.FieldValue;
  status: 'active';
}

export interface ActivationDoc {
  licenseHash: string;
  machineIdHash: string;
  status: ActivationStatus;
  activatedAt: FirebaseFirestore.Timestamp | FirebaseFirestore.FieldValue;
  lastValidatedAt: FirebaseFirestore.Timestamp | FirebaseFirestore.FieldValue;
  revokedAt: FirebaseFirestore.Timestamp | null;
  tokenVersion: number;
}

export interface AuditLogDoc {
  event: AuditEventType;
  licenseHash: string;
  machineIdHash?: string;
  timestamp: FirebaseFirestore.Timestamp | FirebaseFirestore.FieldValue;
  metadata?: Record<string, any>;
}

export interface SignedTokenPayload {
  v: number;               // Version (2)
  p: string;               // Product ("voca-basic")
  lid: string;             // License identifier (hash prefix or opaque id)
  mid: string;             // SHA-256(machineId)
  plan: LicensePlan;       // "lifetime" | "time_limited"
  iat: number;             // Issued at (unix seconds)
  exp: number | null;      // License expiration (unix seconds or null)
  val: number;             // Lease valid until (unix seconds)
  cust?: string;           // Customer descriptor
}

export interface ActivateRequest {
  licenseKey: string;
  machineId: string;
  appVersion?: string;
}

export interface ActivateResponse {
  ok: boolean;
  activationToken?: string;
  status: string;
  plan?: LicensePlan;
  expiresAt?: string | null;
  validationUntil?: string;
  message?: string;
  errorCode?: string;
}

export interface ValidateRequest {
  activationToken: string;
  machineId: string;
}

export interface ValidateResponse {
  ok: boolean;
  activationToken?: string;
  status: string;
  plan?: LicensePlan;
  expiresAt?: string | null;
  validationUntil?: string;
  message?: string;
  errorCode?: string;
}

export interface DeactivateRequest {
  activationToken: string;
  machineId: string;
}

export interface DeactivateResponse {
  ok: boolean;
  message: string;
  errorCode?: string;
}

export interface AdminCreateLicenseRequest {
  plan?: LicensePlan;
  maxDevices?: number;
  customerId?: string;
  days?: number;
  notes?: string;
}

export interface AdminCreateLicenseResponse {
  ok: boolean;
  licenseKey: string;
  licenseHash: string;
  plan: LicensePlan;
  maxDevices: number;
  expiresAt: string | null;
  customerId: string;
}
