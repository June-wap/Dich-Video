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
exports.getActivationId = getActivationId;
exports.activateLicense = activateLicense;
exports.validateLicense = validateLicense;
exports.deactivateLicense = deactivateLicense;
const admin = __importStar(require("firebase-admin"));
const cryptoService_1 = require("./cryptoService");
const config_1 = require("../config");
const db = () => admin.firestore();
/**
 * Tính activation ID duy nhất cho cặp (licenseHash, machineIdHash)
 */
function getActivationId(licenseHash, machineIdHash) {
    const crypto = require('crypto');
    return crypto.createHash('sha256').update(`${licenseHash}:${machineIdHash}`, 'utf8').digest('hex');
}
/**
 * Xử lý kích hoạt License (Online Activation) với Firestore Transaction
 */
async function activateLicense(req, clientIp) {
    const rawKey = req.licenseKey;
    const machineId = req.machineId;
    if (!rawKey || typeof rawKey !== 'string' || rawKey.trim().length < 10) {
        return {
            ok: false,
            status: 'invalid',
            errorCode: 'LICENSE_INVALID',
            message: 'Mã kích hoạt không đúng định dạng.',
        };
    }
    if (!machineId || typeof machineId !== 'string' || machineId.trim().length < 8) {
        return {
            ok: false,
            status: 'invalid',
            errorCode: 'INVALID_REQUEST',
            message: 'Mã nhận diện máy tính (Machine ID) không hợp lệ.',
        };
    }
    const normalizedKey = (0, cryptoService_1.normalizeLicenseKey)(rawKey);
    const licenseHash = (0, cryptoService_1.hashLicenseKey)(normalizedKey);
    const machineIdHash = (0, cryptoService_1.hashMachineId)(machineId);
    const activationId = getActivationId(licenseHash, machineIdHash);
    const licenseRef = db().collection('licenses').doc(licenseHash);
    const activationRef = db().collection('activations').doc(activationId);
    const deviceRef = db().collection('devices').doc(machineIdHash);
    const auditLogRef = db().collection('auditLogs').doc();
    const nowSeconds = Math.floor(Date.now() / 1000);
    try {
        const result = await db().runTransaction(async (transaction) => {
            const licenseSnap = await transaction.get(licenseRef);
            if (!licenseSnap.exists) {
                return { error: 'LICENSE_INVALID', message: 'Mã bản quyền không tồn tại hoặc đã bị hủy.' };
            }
            const licenseData = licenseSnap.data();
            // 1. Kiểm tra trạng thái License
            if (licenseData.status === 'blocked') {
                return { error: 'LICENSE_BLOCKED', message: 'Mã bản quyền này đã bị khóa do vi phạm chính sách.' };
            }
            if (licenseData.status === 'expired') {
                return { error: 'LICENSE_EXPIRED', message: 'Mã bản quyền này đã hết hạn sử dụng.' };
            }
            // 2. Kiểm tra ngày hết hạn
            if (licenseData.expiresAt) {
                const expiresAtMillis = licenseData.expiresAt.toMillis();
                if (Date.now() > expiresAtMillis) {
                    transaction.update(licenseRef, { status: 'expired' });
                    return { error: 'LICENSE_EXPIRED', message: 'Mã bản quyền này đã hết hạn sử dụng.' };
                }
            }
            // 3. Kiểm tra Activation hiện tại
            const activationSnap = await transaction.get(activationRef);
            const isReactivation = activationSnap.exists && activationSnap.data()?.status === 'active';
            let currentCount = licenseData.activationCount || 0;
            const maxDevices = licenseData.maxDevices || 1;
            if (!isReactivation) {
                // Thiết bị mới kích hoạt -> Kiểm tra device limit
                if (currentCount >= maxDevices) {
                    transaction.set(auditLogRef, {
                        event: 'DEVICE_LIMIT_EXCEEDED',
                        licenseHash,
                        machineIdHash,
                        timestamp: admin.firestore.FieldValue.serverTimestamp(),
                        metadata: {
                            ip: clientIp || null,
                            appVersion: req.appVersion || null,
                            attemptedCount: currentCount + 1,
                            maxDevices,
                        },
                    });
                    return {
                        error: 'DEVICE_LIMIT_REACHED',
                        message: `Mã bản quyền này đã đạt giới hạn tối đa (${maxDevices} máy). Vui lòng gỡ kích hoạt trên máy cũ trước.`,
                    };
                }
                // Tăng activation count
                currentCount += 1;
                transaction.update(licenseRef, {
                    activationCount: currentCount,
                });
                // Tạo / cập nhật activation doc
                const activationPayload = {
                    licenseHash,
                    machineIdHash,
                    status: 'active',
                    activatedAt: admin.firestore.FieldValue.serverTimestamp(),
                    lastValidatedAt: admin.firestore.FieldValue.serverTimestamp(),
                    revokedAt: null,
                    tokenVersion: 2,
                };
                transaction.set(activationRef, activationPayload);
            }
            else {
                // Idempotent reactivation trên cùng một máy
                transaction.update(activationRef, {
                    lastValidatedAt: admin.firestore.FieldValue.serverTimestamp(),
                });
            }
            // 4. Cập nhật thiết bị
            const deviceSnap = await transaction.get(deviceRef);
            if (!deviceSnap.exists) {
                const deviceData = {
                    machineIdHash,
                    firstSeenAt: admin.firestore.FieldValue.serverTimestamp(),
                    lastSeenAt: admin.firestore.FieldValue.serverTimestamp(),
                    status: 'active',
                };
                transaction.set(deviceRef, deviceData);
            }
            else {
                transaction.update(deviceRef, {
                    lastSeenAt: admin.firestore.FieldValue.serverTimestamp(),
                });
            }
            // 5. Ghi Audit Log
            transaction.set(auditLogRef, {
                event: isReactivation ? 'LICENSE_REACTIVATED' : 'LICENSE_ACTIVATED',
                licenseHash,
                machineIdHash,
                timestamp: admin.firestore.FieldValue.serverTimestamp(),
                metadata: {
                    ip: clientIp || null,
                    appVersion: req.appVersion || null,
                    plan: licenseData.plan,
                    activationCount: currentCount,
                },
            });
            return {
                success: true,
                licenseData,
            };
        });
        if ('error' in result) {
            return {
                ok: false,
                status: 'error',
                errorCode: result.error,
                message: result.message,
            };
        }
        const license = result.licenseData;
        const expiresAtSeconds = license.expiresAt ? Math.floor(license.expiresAt.toMillis() / 1000) : null;
        const validationUntilSeconds = nowSeconds + config_1.DEFAULT_LEASE_SECONDS;
        // Ký Ed25519 Token
        const tokenPayload = {
            v: 2,
            p: 'voca-basic',
            lid: licenseHash,
            mid: machineIdHash,
            plan: license.plan,
            iat: nowSeconds,
            exp: expiresAtSeconds,
            val: validationUntilSeconds,
            cust: license.customerId,
        };
        const signedToken = (0, cryptoService_1.signActivationToken)(tokenPayload);
        return {
            ok: true,
            status: 'active',
            activationToken: signedToken,
            plan: license.plan,
            expiresAt: license.expiresAt ? license.expiresAt.toDate().toISOString() : null,
            validationUntil: new Date(validationUntilSeconds * 1000).toISOString(),
            message: 'Kích hoạt bản quyền thành công!',
        };
    }
    catch (error) {
        console.error('activateLicense error:', error);
        return {
            ok: false,
            status: 'error',
            errorCode: 'SERVICE_UNAVAILABLE',
            message: 'Lỗi hệ thống máy chủ khi kích hoạt bản quyền. Vui lòng thử lại sau.',
        };
    }
}
/**
 * Xác thực & làm mới token định kỳ (Validate / Refresh)
 */
async function validateLicense(req, clientIp) {
    const { activationToken, machineId } = req;
    if (!activationToken || !machineId) {
        return {
            ok: false,
            status: 'invalid',
            errorCode: 'INVALID_REQUEST',
            message: 'Thiếu thông tin activationToken hoặc machineId.',
        };
    }
    // 1. Verify token signature
    const tokenVerif = (0, cryptoService_1.verifyActivationToken)(activationToken);
    if (!tokenVerif.valid || !tokenVerif.payload) {
        return {
            ok: false,
            status: 'invalid',
            errorCode: 'TOKEN_INVALID',
            message: 'Token bản quyền không hợp lệ hoặc đã bị chỉnh sửa.',
        };
    }
    const tokenPayload = tokenVerif.payload;
    const machineIdHash = (0, cryptoService_1.hashMachineId)(machineId);
    // 2. Check machine match
    if (tokenPayload.mid !== machineIdHash) {
        return {
            ok: false,
            status: 'invalid',
            errorCode: 'MACHINE_MISMATCH',
            message: 'Mã nhận diện máy tính không khớp với token bản quyền.',
        };
    }
    const licenseHash = tokenPayload.lid;
    const activationId = getActivationId(licenseHash, machineIdHash);
    try {
        const activationSnap = await db().collection('activations').doc(activationId).get();
        if (!activationSnap.exists || activationSnap.data()?.status !== 'active') {
            return {
                ok: false,
                status: 'revoked',
                errorCode: 'ACTIVATION_REVOKED',
                message: 'Bản quyền trên thiết bị này đã bị thu hồi.',
            };
        }
        const licenseSnap = await db().collection('licenses').doc(licenseHash).get();
        if (!licenseSnap.exists) {
            return {
                ok: false,
                status: 'invalid',
                errorCode: 'LICENSE_INVALID',
                message: 'Mã bản quyền không còn tồn tại trên hệ thống.',
            };
        }
        const licenseData = licenseSnap.data();
        if (licenseData.status === 'blocked') {
            return {
                ok: false,
                status: 'blocked',
                errorCode: 'LICENSE_BLOCKED',
                message: 'Bản quyền này đã bị khóa trên hệ thống.',
            };
        }
        if (licenseData.expiresAt && Date.now() > licenseData.expiresAt.toMillis()) {
            return {
                ok: false,
                status: 'expired',
                errorCode: 'LICENSE_EXPIRED',
                message: 'Bản quyền này đã hết hạn sử dụng.',
            };
        }
        // Cập nhật lastValidatedAt
        await db().collection('activations').doc(activationId).update({
            lastValidatedAt: admin.firestore.FieldValue.serverTimestamp(),
        });
        const nowSeconds = Math.floor(Date.now() / 1000);
        const expiresAtSeconds = licenseData.expiresAt
            ? Math.floor(licenseData.expiresAt.toMillis() / 1000)
            : null;
        const validationUntilSeconds = nowSeconds + config_1.DEFAULT_LEASE_SECONDS;
        // Issue refreshed token
        const refreshedPayload = {
            v: 2,
            p: 'voca-basic',
            lid: licenseHash,
            mid: machineIdHash,
            plan: licenseData.plan,
            iat: nowSeconds,
            exp: expiresAtSeconds,
            val: validationUntilSeconds,
            cust: licenseData.customerId,
        };
        const refreshedToken = (0, cryptoService_1.signActivationToken)(refreshedPayload);
        return {
            ok: true,
            status: 'active',
            activationToken: refreshedToken,
            plan: licenseData.plan,
            expiresAt: licenseData.expiresAt ? licenseData.expiresAt.toDate().toISOString() : null,
            validationUntil: new Date(validationUntilSeconds * 1000).toISOString(),
            message: 'Bản quyền hợp lệ và đã được làm mới.',
        };
    }
    catch (error) {
        console.error('validateLicense error:', error);
        return {
            ok: false,
            status: 'error',
            errorCode: 'SERVICE_UNAVAILABLE',
            message: 'Không thể xác thực trực tuyến với máy chủ bản quyền.',
        };
    }
}
/**
 * Hủy kích hoạt bản quyền trên thiết bị (Deactivate)
 */
async function deactivateLicense(req, clientIp) {
    const { activationToken, machineId } = req;
    if (!activationToken || !machineId) {
        return {
            ok: false,
            errorCode: 'INVALID_REQUEST',
            message: 'Thiếu thông tin activationToken hoặc machineId.',
        };
    }
    const tokenVerif = (0, cryptoService_1.verifyActivationToken)(activationToken);
    if (!tokenVerif.valid || !tokenVerif.payload) {
        return {
            ok: false,
            errorCode: 'TOKEN_INVALID',
            message: 'Token bản quyền không hợp lệ.',
        };
    }
    const tokenPayload = tokenVerif.payload;
    const machineIdHash = (0, cryptoService_1.hashMachineId)(machineId);
    if (tokenPayload.mid !== machineIdHash) {
        return {
            ok: false,
            errorCode: 'MACHINE_MISMATCH',
            message: 'Không thể hủy kích hoạt từ thiết bị khác.',
        };
    }
    const licenseHash = tokenPayload.lid;
    const activationId = getActivationId(licenseHash, machineIdHash);
    const licenseRef = db().collection('licenses').doc(licenseHash);
    const activationRef = db().collection('activations').doc(activationId);
    const auditLogRef = db().collection('auditLogs').doc();
    try {
        await db().runTransaction(async (transaction) => {
            const activationSnap = await transaction.get(activationRef);
            if (!activationSnap.exists || activationSnap.data()?.status !== 'active') {
                return; // Đã deactivate trước đó
            }
            transaction.update(activationRef, {
                status: 'revoked',
                revokedAt: admin.firestore.FieldValue.serverTimestamp(),
            });
            const licenseSnap = await transaction.get(licenseRef);
            if (licenseSnap.exists) {
                const count = licenseSnap.data()?.activationCount || 0;
                transaction.update(licenseRef, {
                    activationCount: Math.max(0, count - 1),
                });
            }
            transaction.set(auditLogRef, {
                event: 'LICENSE_DEACTIVATED',
                licenseHash,
                machineIdHash,
                timestamp: admin.firestore.FieldValue.serverTimestamp(),
                metadata: { ip: clientIp || null },
            });
        });
        return {
            ok: true,
            message: 'Hủy kích hoạt bản quyền trên thiết bị này thành công.',
        };
    }
    catch (error) {
        console.error('deactivateLicense error:', error);
        return {
            ok: false,
            errorCode: 'SERVICE_UNAVAILABLE',
            message: 'Lỗi khi hủy kích hoạt bản quyền.',
        };
    }
}
//# sourceMappingURL=licenseService.js.map