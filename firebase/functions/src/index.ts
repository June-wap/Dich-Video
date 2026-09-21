import * as admin from 'firebase-admin';
import * as functions from 'firebase-functions';
import cors from 'cors';
import { activateLicense, validateLicense, deactivateLicense } from './services/licenseService';
import * as adminService from './services/adminService';
import { requireAdminAuth } from './middleware/auth';
import { getEd25519PublicKeyHex } from './config';

// Khởi tạo Firebase Admin SDK nếu chưa khởi tạo
if (!admin.apps.length) {
  admin.initializeApp();
}

const corsHandler = cors({ origin: true });

/**
 * Public Endpoint: Kích hoạt bản quyền trực tuyến
 * POST /activateLicense
 */
export const activateLicenseEndpoint = functions.https.onRequest((req, res) => {
  corsHandler(req, res, async () => {
    if (req.method !== 'POST') {
      res.status(405).json({ ok: false, errorCode: 'METHOD_NOT_ALLOWED', message: 'Method Not Allowed' });
      return;
    }

    try {
      const clientIp = (req.headers['x-forwarded-for'] as string) || req.socket.remoteAddress;
      const result = await activateLicense(req.body, clientIp);
      const statusCode = result.ok ? 200 : result.errorCode === 'DEVICE_LIMIT_REACHED' ? 409 : 400;
      res.status(statusCode).json(result);
    } catch (err: any) {
      console.error('activateLicenseEndpoint error:', err);
      res.status(500).json({ ok: false, errorCode: 'INTERNAL_ERROR', message: err.message });
    }
  });
});

/**
 * Public Endpoint: Xác thực & làm mới token định kỳ
 * POST /validateLicense
 */
export const validateLicenseEndpoint = functions.https.onRequest((req, res) => {
  corsHandler(req, res, async () => {
    if (req.method !== 'POST') {
      res.status(405).json({ ok: false, errorCode: 'METHOD_NOT_ALLOWED', message: 'Method Not Allowed' });
      return;
    }

    try {
      const clientIp = (req.headers['x-forwarded-for'] as string) || req.socket.remoteAddress;
      const result = await validateLicense(req.body, clientIp);
      const statusCode = result.ok ? 200 : 403;
      res.status(statusCode).json(result);
    } catch (err: any) {
      console.error('validateLicenseEndpoint error:', err);
      res.status(500).json({ ok: false, errorCode: 'INTERNAL_ERROR', message: err.message });
    }
  });
});

/**
 * Public Endpoint: Hủy kích hoạt trên thiết bị
 * POST /deactivateLicense
 */
export const deactivateLicenseEndpoint = functions.https.onRequest((req, res) => {
  corsHandler(req, res, async () => {
    if (req.method !== 'POST') {
      res.status(405).json({ ok: false, errorCode: 'METHOD_NOT_ALLOWED', message: 'Method Not Allowed' });
      return;
    }

    try {
      const clientIp = (req.headers['x-forwarded-for'] as string) || req.socket.remoteAddress;
      const result = await deactivateLicense(req.body, clientIp);
      const statusCode = result.ok ? 200 : 400;
      res.status(statusCode).json(result);
    } catch (err: any) {
      console.error('deactivateLicenseEndpoint error:', err);
      res.status(500).json({ ok: false, errorCode: 'INTERNAL_ERROR', message: err.message });
    }
  });
});

/**
 * Public Endpoint: Lấy Ed25519 Public Key để client cấu hình / verify
 * GET /publicKey
 */
export const getPublicKeyEndpoint = functions.https.onRequest((req, res) => {
  corsHandler(req, res, () => {
    try {
      const pubHex = getEd25519PublicKeyHex();
      res.status(200).json({ ok: true, publicKeyHex: pubHex, algorithm: 'Ed25519' });
    } catch (err: any) {
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
export const adminCreateLicense = functions.https.onRequest((req, res) => {
  corsHandler(req, res, () => {
    requireAdminAuth(req, res, async () => {
      try {
        const result = await adminService.createLicense(req.body);
        res.status(200).json(result);
      } catch (err: any) {
        res.status(500).json({ ok: false, message: err.message });
      }
    });
  });
});

/**
 * Admin: Khóa License
 * POST /adminBlockLicense
 */
export const adminBlockLicense = functions.https.onRequest((req, res) => {
  corsHandler(req, res, () => {
    requireAdminAuth(req, res, async () => {
      try {
        const { licenseKeyOrHash, reason } = req.body;
        if (!licenseKeyOrHash) {
          res.status(400).json({ ok: false, message: 'Thiếu licenseKeyOrHash' });
          return;
        }
        const result = await adminService.blockLicense(licenseKeyOrHash, reason);
        res.status(200).json(result);
      } catch (err: any) {
        res.status(500).json({ ok: false, message: err.message });
      }
    });
  });
});

/**
 * Admin: Mở khóa License
 * POST /adminUnblockLicense
 */
export const adminUnblockLicense = functions.https.onRequest((req, res) => {
  corsHandler(req, res, () => {
    requireAdminAuth(req, res, async () => {
      try {
        const { licenseKeyOrHash } = req.body;
        if (!licenseKeyOrHash) {
          res.status(400).json({ ok: false, message: 'Thiếu licenseKeyOrHash' });
          return;
        }
        const result = await adminService.unblockLicense(licenseKeyOrHash);
        res.status(200).json(result);
      } catch (err: any) {
        res.status(500).json({ ok: false, message: err.message });
      }
    });
  });
});

/**
 * Admin: Gia hạn License
 * POST /adminExtendLicense
 */
export const adminExtendLicense = functions.https.onRequest((req, res) => {
  corsHandler(req, res, () => {
    requireAdminAuth(req, res, async () => {
      try {
        const { licenseKeyOrHash, additionalDays } = req.body;
        if (!licenseKeyOrHash || !additionalDays) {
          res.status(400).json({ ok: false, message: 'Thiếu licenseKeyOrHash hoặc additionalDays' });
          return;
        }
        const result = await adminService.extendLicense(licenseKeyOrHash, Number(additionalDays));
        res.status(200).json(result);
      } catch (err: any) {
        res.status(500).json({ ok: false, message: err.message });
      }
    });
  });
});

/**
 * Admin: Thu hồi Activation của thiết bị (Revoke / Device Reset)
 * POST /adminRevokeActivation
 */
export const adminRevokeActivation = functions.https.onRequest((req, res) => {
  corsHandler(req, res, () => {
    requireAdminAuth(req, res, async () => {
      try {
        const { licenseKeyOrHash, machineId } = req.body;
        if (!licenseKeyOrHash || !machineId) {
          res.status(400).json({ ok: false, message: 'Thiếu licenseKeyOrHash hoặc machineId' });
          return;
        }
        const result = await adminService.revokeActivation(licenseKeyOrHash, machineId);
        res.status(200).json(result);
      } catch (err: any) {
        res.status(500).json({ ok: false, message: err.message });
      }
    });
  });
});

/**
 * Admin: Xem danh sách activations của 1 license
 * POST /adminListActivations
 */
export const adminListActivations = functions.https.onRequest((req, res) => {
  corsHandler(req, res, () => {
    requireAdminAuth(req, res, async () => {
      try {
        const { licenseKeyOrHash } = req.body;
        if (!licenseKeyOrHash) {
          res.status(400).json({ ok: false, message: 'Thiếu licenseKeyOrHash' });
          return;
        }
        const result = await adminService.listActivations(licenseKeyOrHash);
        res.status(200).json(result);
      } catch (err: any) {
        res.status(500).json({ ok: false, message: err.message });
      }
    });
  });
});
