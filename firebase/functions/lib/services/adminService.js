"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.createLicense = createLicense;
exports.blockLicense = blockLicense;
exports.unblockLicense = unblockLicense;
exports.extendLicense = extendLicense;
exports.revokeActivation = revokeActivation;
exports.listActivations = listActivations;
const admin = __importStar(require("firebase-admin"));
const cryptoService_1 = require("./cryptoService");
const licenseService_1 = require("./licenseService");
const db = () => admin.firestore();
/**
 * Admin: Tạo License mới với CSPRNG key
 * Lưu ý: Plaintext licenseKey chỉ hiển thị duy nhất 1 lần khi tạo, không lưu vào Firestore!
 */
async function createLicense(req) {
    const plan = req.plan === 'time_limited' ? 'time_limited' : 'lifetime';
    const maxDevices = Math.max(1, req.maxDevices || 1);
    const customerId = (req.customerId || 'Khách hàng').trim();
    const rawKey = (0, cryptoService_1.generateLicenseKey)();
    const normalizedKey = (0, cryptoService_1.normalizeLicenseKey)(rawKey);
    const licenseHash = (0, cryptoService_1.hashLicenseKey)(normalizedKey);
    let expiresAt = null;
    if (plan === 'time_limited') {
        const days = Math.max(1, req.days || 30);
        const expireDate = new Date(Date.now() + days * 24 * 60 * 60 * 1000);
        expiresAt = admin.firestore.Timestamp.fromDate(expireDate);
    }
    const licenseDoc = {
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
async function blockLicense(licenseKeyOrHash, reason) {
    const clean = licenseKeyOrHash.trim();
    const licenseHash = clean.startsWith('VB-') ? (0, cryptoService_1.hashLicenseKey)((0, cryptoService_1.normalizeLicenseKey)(clean)) : clean;
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
async function unblockLicense(licenseKeyOrHash) {
    const clean = licenseKeyOrHash.trim();
    const licenseHash = clean.startsWith('VB-') ? (0, cryptoService_1.hashLicenseKey)((0, cryptoService_1.normalizeLicenseKey)(clean)) : clean;
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
async function extendLicense(licenseKeyOrHash, additionalDays) {
    const clean = licenseKeyOrHash.trim();
    const licenseHash = clean.startsWith('VB-') ? (0, cryptoService_1.hashLicenseKey)((0, cryptoService_1.normalizeLicenseKey)(clean)) : clean;
    const licenseRef = db().collection('licenses').doc(licenseHash);
    const snap = await licenseRef.get();
    if (!snap.exists) {
        throw new Error('LICENSE_NOT_FOUND');
    }
    const data = snap.data();
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
async function revokeActivation(licenseKeyOrHash, machineId) {
    const clean = licenseKeyOrHash.trim();
    const licenseHash = clean.startsWith('VB-') ? (0, cryptoService_1.hashLicenseKey)((0, cryptoService_1.normalizeLicenseKey)(clean)) : clean;
    const machineIdHash = (0, cryptoService_1.hashMachineId)(machineId);
    const activationId = (0, licenseService_1.getActivationId)(licenseHash, machineIdHash);
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
async function listActivations(licenseKeyOrHash) {
    const clean = licenseKeyOrHash.trim();
    const licenseHash = clean.startsWith('VB-') ? (0, cryptoService_1.hashLicenseKey)((0, cryptoService_1.normalizeLicenseKey)(clean)) : clean;
    const snaps = await db().collection('activations').where('licenseHash', '==', licenseHash).get();
    const activations = [];
    snaps.forEach((doc) => {
        activations.push({ id: doc.id, ...doc.data() });
    });
    return { ok: true, licenseHash, activations };
}
//# sourceMappingURL=adminService.js.map