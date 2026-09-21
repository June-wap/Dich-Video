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
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.adminListActivations = exports.adminRevokeActivation = exports.adminExtendLicense = exports.adminUnblockLicense = exports.adminBlockLicense = exports.adminCreateLicense = exports.getPublicKeyEndpoint = exports.deactivateLicenseEndpoint = exports.validateLicenseEndpoint = exports.activateLicenseEndpoint = void 0;
const admin = __importStar(require("firebase-admin"));
const functions = __importStar(require("firebase-functions"));
const cors_1 = __importDefault(require("cors"));
const licenseService_1 = require("./services/licenseService");
const adminService = __importStar(require("./services/adminService"));
const auth_1 = require("./middleware/auth");
const config_1 = require("./config");
// Khởi tạo Firebase Admin SDK nếu chưa khởi tạo
if (!admin.apps.length) {
    admin.initializeApp();
}
const corsHandler = (0, cors_1.default)({ origin: true });
/**
 * Public Endpoint: Kích hoạt bản quyền trực tuyến
 * POST /activateLicense
 */
exports.activateLicenseEndpoint = functions.https.onRequest((req, res) => {
    corsHandler(req, res, async () => {
        if (req.method !== 'POST') {
            res.status(405).json({ ok: false, errorCode: 'METHOD_NOT_ALLOWED', message: 'Method Not Allowed' });
            return;
        }
        try {
            const clientIp = req.headers['x-forwarded-for'] || req.socket.remoteAddress;
            const result = await (0, licenseService_1.activateLicense)(req.body, clientIp);
            const statusCode = result.ok ? 200 : result.errorCode === 'DEVICE_LIMIT_REACHED' ? 409 : 400;
            res.status(statusCode).json(result);
        }
        catch (err) {
            console.error('activateLicenseEndpoint error:', err);
            res.status(500).json({ ok: false, errorCode: 'INTERNAL_ERROR', message: err.message });
        }
    });
});
/**
 * Public Endpoint: Xác thực & làm mới token định kỳ
 * POST /validateLicense
 */
exports.validateLicenseEndpoint = functions.https.onRequest((req, res) => {
    corsHandler(req, res, async () => {
        if (req.method !== 'POST') {
            res.status(405).json({ ok: false, errorCode: 'METHOD_NOT_ALLOWED', message: 'Method Not Allowed' });
            return;
        }
        try {
            const clientIp = req.headers['x-forwarded-for'] || req.socket.remoteAddress;
            const result = await (0, licenseService_1.validateLicense)(req.body, clientIp);
            const statusCode = result.ok ? 200 : 403;
            res.status(statusCode).json(result);
        }
        catch (err) {
            console.error('validateLicenseEndpoint error:', err);
            res.status(500).json({ ok: false, errorCode: 'INTERNAL_ERROR', message: err.message });
        }
    });
});
/**
 * Public Endpoint: Hủy kích hoạt trên thiết bị
 * POST /deactivateLicense
 */
exports.deactivateLicenseEndpoint = functions.https.onRequest((req, res) => {
    corsHandler(req, res, async () => {
        if (req.method !== 'POST') {
            res.status(405).json({ ok: false, errorCode: 'METHOD_NOT_ALLOWED', message: 'Method Not Allowed' });
            return;
        }
        try {
            const clientIp = req.headers['x-forwarded-for'] || req.socket.remoteAddress;
            const result = await (0, licenseService_1.deactivateLicense)(req.body, clientIp);
            const statusCode = result.ok ? 200 : 400;
            res.status(statusCode).json(result);
        }
        catch (err) {
            console.error('deactivateLicenseEndpoint error:', err);
            res.status(500).json({ ok: false, errorCode: 'INTERNAL_ERROR', message: err.message });
        }
    });
});
/**
 * Public Endpoint: Lấy Ed25519 Public Key để client cấu hình / verify
 * GET /publicKey
 */
exports.getPublicKeyEndpoint = functions.https.onRequest((req, res) => {
    corsHandler(req, res, () => {
        try {
            const pubHex = (0, config_1.getEd25519PublicKeyHex)();
            res.status(200).json({ ok: true, publicKeyHex: pubHex, algorithm: 'Ed25519' });
        }
        catch (err) {
            res.status(500).json({ ok: false, message: err.message });
        }
    });
});
// ==========================================
// ADMIN-ONLY ENDPOINTS (Bảo vệ bởi requireAdminAuth)
// ==========================================
/**
 * Admin: Tạo License mới
 * POST /adminCreateLicense
 */
exports.adminCreateLicense = functions.https.onRequest((req, res) => {
    corsHandler(req, res, () => {
        (0, auth_1.requireAdminAuth)(req, res, async () => {
            try {
                const result = await adminService.createLicense(req.body);
                res.status(200).json(result);
            }
            catch (err) {
                res.status(500).json({ ok: false, message: err.message });
            }
        });
    });
});
/**
 * Admin: Khóa License
 * POST /adminBlockLicense
 */
exports.adminBlockLicense = functions.https.onRequest((req, res) => {
    corsHandler(req, res, () => {
        (0, auth_1.requireAdminAuth)(req, res, async () => {
            try {
                const { licenseKeyOrHash, reason } = req.body;
                if (!licenseKeyOrHash) {
                    res.status(400).json({ ok: false, message: 'Thiếu licenseKeyOrHash' });
                    return;
                }
                const result = await adminService.blockLicense(licenseKeyOrHash, reason);
                res.status(200).json(result);
            }
            catch (err) {
                res.status(500).json({ ok: false, message: err.message });
            }
        });
    });
});
/**
 * Admin: Mở khóa License
 * POST /adminUnblockLicense
 */
exports.adminUnblockLicense = functions.https.onRequest((req, res) => {
    corsHandler(req, res, () => {
        (0, auth_1.requireAdminAuth)(req, res, async () => {
            try {
                const { licenseKeyOrHash } = req.body;
                if (!licenseKeyOrHash) {
                    res.status(400).json({ ok: false, message: 'Thiếu licenseKeyOrHash' });
                    return;
                }
                const result = await adminService.unblockLicense(licenseKeyOrHash);
                res.status(200).json(result);
            }
            catch (err) {
                res.status(500).json({ ok: false, message: err.message });
            }
        });
    });
});
/**
 * Admin: Gia hạn License
 * POST /adminExtendLicense
 */
exports.adminExtendLicense = functions.https.onRequest((req, res) => {
    corsHandler(req, res, () => {
        (0, auth_1.requireAdminAuth)(req, res, async () => {
            try {
                const { licenseKeyOrHash, additionalDays } = req.body;
                if (!licenseKeyOrHash || !additionalDays) {
                    res.status(400).json({ ok: false, message: 'Thiếu licenseKeyOrHash hoặc additionalDays' });
                    return;
                }
                const result = await adminService.extendLicense(licenseKeyOrHash, Number(additionalDays));
                res.status(200).json(result);
            }
            catch (err) {
                res.status(500).json({ ok: false, message: err.message });
            }
        });
    });
});
/**
 * Admin: Thu hồi Activation của thiết bị (Revoke / Device Reset)
 * POST /adminRevokeActivation
 */
exports.adminRevokeActivation = functions.https.onRequest((req, res) => {
    corsHandler(req, res, () => {
        (0, auth_1.requireAdminAuth)(req, res, async () => {
            try {
                const { licenseKeyOrHash, machineId } = req.body;
                if (!licenseKeyOrHash || !machineId) {
                    res.status(400).json({ ok: false, message: 'Thiếu licenseKeyOrHash hoặc machineId' });
                    return;
                }
                const result = await adminService.revokeActivation(licenseKeyOrHash, machineId);
                res.status(200).json(result);
            }
            catch (err) {
                res.status(500).json({ ok: false, message: err.message });
            }
        });
    });
});
/**
 * Admin: Xem danh sách activations của 1 license
 * POST /adminListActivations
 */
exports.adminListActivations = functions.https.onRequest((req, res) => {
    corsHandler(req, res, () => {
        (0, auth_1.requireAdminAuth)(req, res, async () => {
            try {
                const { licenseKeyOrHash } = req.body;
                if (!licenseKeyOrHash) {
                    res.status(400).json({ ok: false, message: 'Thiếu licenseKeyOrHash' });
                    return;
                }
                const result = await adminService.listActivations(licenseKeyOrHash);
                res.status(200).json(result);
            }
            catch (err) {
                res.status(500).json({ ok: false, message: err.message });
            }
        });
    });
});
//# sourceMappingURL=index.js.map