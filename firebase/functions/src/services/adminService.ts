import * as admin from 'firebase-admin';
import {
  AdminCreateLicenseRequest,
  AdminCreateLicenseResponse,
  LicenseDoc,
  LicensePlan,
} from '../types';
import {
  generateLicenseKey,
  hashLicenseKey,
  normalizeLicenseKey,
  hashMachineId,
} from './cryptoService';
import { getActivationId } from './licenseService';

const db = () => admin.firestore();

/**
 * Admin: Tạo License mới với CSPRNG key
 * Lưu ý: Plaintext licenseKey chỉ hiển thị duy nhất 1 lần khi tạo, không lưu vào Firestore!
 */
export async function createLicense(
  req: AdminCreateLicenseRequest
): Promise<AdminCreateLicenseResponse> {
  const plan: LicensePlan = req.plan === 'time_limited' ? 'time_limited' : 'lifetime';
  const maxDevices = Math.max(1, req.maxDevices || 1);
  const customerId = (req.customerId || 'Khách hàng').trim();

  const rawKey = generateLicenseKey();
  const normalizedKey = normalizeLicenseKey(rawKey);
  const licenseHash = hashLicenseKey(normalizedKey);

  let expiresAt: admin.firestore.Timestamp | null = null;
  if (plan === 'time_limited') {
    const days = Math.max(1, req.days || 30);
    const expireDate = new Date(Date.now() + days * 24 * 60 * 60 * 1000);
    expiresAt = admin.firestore.Timestamp.fromDate(expireDate);
  }

  const licenseDoc: LicenseDoc = {
    status: 'active',
    plan,
    maxDevices,
    activationCount: 0,
    customerId,
    createdAt: admin.firestore.FieldValue.serverTimestamp(),
    expiresAt,
    metadata: {
      product: 'voca-basic',
      version: 2,
      notes: req.notes || '',
    },
  };

  await db().collection('licenses').doc(licenseHash).set(licenseDoc);

  await db().collection('auditLogs').add({
    event: 'LICENSE_CREATED',
    licenseHash,
    timestamp: admin.firestore.FieldValue.serverTimestamp(),
    metadata: {
      plan,
      maxDevices,
      customerId,
    },
  });

  return {
    ok: true,
    licenseKey: rawKey,
    licenseHash,
    plan,
    maxDevices,
    expiresAt: expiresAt ? expiresAt.toDate().toISOString() : null,
    customerId,
  };
}

/**
 * Admin: Khóa mã bản quyền (Block)
 */
export async function blockLicense(licenseKeyOrHash: string, reason?: string) {
  const clean = licenseKeyOrHash.trim();
  const licenseHash = clean.startsWith('VB-') ? hashLicenseKey(normalizeLicenseKey(clean)) : clean;

  const licenseRef = db().collection('licenses').doc(licenseHash);
  const snap = await licenseRef.get();
  if (!snap.exists) {
    throw new Error('LICENSE_NOT_FOUND');
  }

  await licenseRef.update({
    status: 'blocked',
    'metadata.blockedReason': reason || 'Admin blocked',
    'metadata.blockedAt': admin.firestore.FieldValue.serverTimestamp(),
  });

  await db().collection('auditLogs').add({
    event: 'LICENSE_BLOCKED',
    licenseHash,
    timestamp: admin.firestore.FieldValue.serverTimestamp(),
    metadata: { reason },
  });

  return { ok: true, licenseHash, status: 'blocked' };
}

/**
 * Admin: Mở khóa mã bản quyền (Unblock)
 */
export async function unblockLicense(licenseKeyOrHash: string) {
  const clean = licenseKeyOrHash.trim();
  const licenseHash = clean.startsWith('VB-') ? hashLicenseKey(normalizeLicenseKey(clean)) : clean;

  const licenseRef = db().collection('licenses').doc(licenseHash);
  const snap = await licenseRef.get();
  if (!snap.exists) {
    throw new Error('LICENSE_NOT_FOUND');
  }

  await licenseRef.update({
    status: 'active',
    'metadata.unblockedAt': admin.firestore.FieldValue.serverTimestamp(),
  });

  await db().collection('auditLogs').add({
    event: 'LICENSE_UNBLOCKED',
    licenseHash,
    timestamp: admin.firestore.FieldValue.serverTimestamp(),
  });

  return { ok: true, licenseHash, status: 'active' };
}

/**
 * Admin: Gia hạn thời gian sử dụng License
 */
export async function extendLicense(licenseKeyOrHash: string, additionalDays: number) {
  const clean = licenseKeyOrHash.trim();
  const licenseHash = clean.startsWith('VB-') ? hashLicenseKey(normalizeLicenseKey(clean)) : clean;

  const licenseRef = db().collection('licenses').doc(licenseHash);
  const snap = await licenseRef.get();
  if (!snap.exists) {
    throw new Error('LICENSE_NOT_FOUND');
  }

  const data = snap.data() as LicenseDoc;
  const currentExpiry = data.expiresAt ? data.expiresAt.toMillis() : Date.now();
  const newExpiry = new Date(Math.max(Date.now(), currentExpiry) + additionalDays * 24 * 60 * 60 * 1000);
  const newTimestamp = admin.firestore.Timestamp.fromDate(newExpiry);

  await licenseRef.update({
    status: 'active',
    expiresAt: newTimestamp,
    plan: 'time_limited',
  });

  await db().collection('auditLogs').add({
    event: 'LICENSE_EXTENDED',
    licenseHash,
    timestamp: admin.firestore.FieldValue.serverTimestamp(),
    metadata: { additionalDays, newExpiresAt: newExpiry.toISOString() },
  });

  return { ok: true, licenseHash, newExpiresAt: newExpiry.toISOString() };
}

/**
 * Admin: Thu hồi kích hoạt của 1 thiết bị cụ thể (Revoke / Reset Device)
 */
export async function revokeActivation(licenseKeyOrHash: string, machineId: string) {
  const clean = licenseKeyOrHash.trim();
  const licenseHash = clean.startsWith('VB-') ? hashLicenseKey(normalizeLicenseKey(clean)) : clean;
  const machineIdHash = hashMachineId(machineId);
  const activationId = getActivationId(licenseHash, machineIdHash);

  const licenseRef = db().collection('licenses').doc(licenseHash);
  const activationRef = db().collection('activations').doc(activationId);

  await db().runTransaction(async (transaction) => {
    const actSnap = await transaction.get(activationRef);
    if (!actSnap.exists || actSnap.data()?.status !== 'active') {
      return;
    }

    transaction.update(activationRef, {
      status: 'revoked',
      revokedAt: admin.firestore.FieldValue.serverTimestamp(),
    });

    const licSnap = await transaction.get(licenseRef);
    if (licSnap.exists) {
      const count = licSnap.data()?.activationCount || 0;
      transaction.update(licenseRef, {
        activationCount: Math.max(0, count - 1),
      });
    }

    transaction.set(db().collection('auditLogs').doc(), {
      event: 'LICENSE_REVOKED',
      licenseHash,
      machineIdHash,
      timestamp: admin.firestore.FieldValue.serverTimestamp(),
      metadata: { adminAction: true },
    });
  });

  return { ok: true, licenseHash, machineIdHash, status: 'revoked' };
}

/**
 * Admin: Liệt kê các activation của 1 license
 */
export async function listActivations(licenseKeyOrHash: string) {
  const clean = licenseKeyOrHash.trim();
  const licenseHash = clean.startsWith('VB-') ? hashLicenseKey(normalizeLicenseKey(clean)) : clean;

  const snaps = await db().collection('activations').where('licenseHash', '==', licenseHash).get();
  const activations: any[] = [];
  snaps.forEach((doc) => {
    activations.push({ id: doc.id, ...doc.data() });
  });

  return { ok: true, licenseHash, activations };
}
