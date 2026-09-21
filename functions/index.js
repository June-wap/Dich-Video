"use strict";

const admin = require("firebase-admin");
const { onRequest } = require("firebase-functions/v2/https");
const { setGlobalOptions } = require("firebase-functions/v2");
const { getEd25519PublicKeyHex } = require("./crypto");
const { activateLicense, validateLicense, deactivateLicense } = require("./licenseService");
const adminService = require("./adminService");

if (!admin.apps.length) {
  admin.initializeApp();
}

setGlobalOptions({ maxInstances: 10 });

function handleCors(req, res) {
  res.set("Access-Control-Allow-Origin", "*");
  res.set("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  res.set("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Admin-Key");
  if (req.method === "OPTIONS") {
    res.status(204).send("");
    return true;
  }
  return false;
}

function verifyAdminAuth(req, res) {
  const adminKey = req.headers["x-admin-key"] || (req.query && req.query.adminKey);
  const expectedKey = process.env.ADMIN_API_KEY || "voca-basic-default-admin-secret-change-in-production";

  if (!adminKey || typeof adminKey !== "string") {
    res.status(401).json({ ok: false, errorCode: "UNAUTHORIZED", message: "Thiếu X-Admin-Key header." });
    return false;
  }

  const crypto = require("crypto");
  const providedBuf = Buffer.from(adminKey);
  const expectedBuf = Buffer.from(expectedKey);

  if (providedBuf.length !== expectedBuf.length || !crypto.timingSafeEqual(providedBuf, expectedBuf)) {
    res.status(403).json({ ok: false, errorCode: "UNAUTHORIZED", message: "Mã xác thực quản trị không chính xác." });
    return false;
  }

  return true;
}

/**
 * Public Endpoint: Kích hoạt bản quyền (POST /activate-license hoặc /activateLicense)
 */
exports.activateLicense = onRequest(async (req, res) => {
  if (handleCors(req, res)) return;
  if (req.method !== "POST") {
    res.status(405).json({ ok: false, errorCode: "METHOD_NOT_ALLOWED", message: "Method Not Allowed" });
    return;
  }

  const clientIp = req.headers["x-forwarded-for"] || req.socket.remoteAddress;
  const result = await activateLicense(req.body, clientIp);
  const statusCode = result.ok ? 200 : result.errorCode === "DEVICE_LIMIT_REACHED" ? 409 : 400;
  res.status(statusCode).json(result);
});

/**
 * Public Endpoint: Xác thực và gia hạn lease token (POST /validate-license hoặc /validateLicense)
 */
exports.validateLicense = onRequest(async (req, res) => {
  if (handleCors(req, res)) return;
  if (req.method !== "POST") {
    res.status(405).json({ ok: false, errorCode: "METHOD_NOT_ALLOWED", message: "Method Not Allowed" });
    return;
  }

  const clientIp = req.headers["x-forwarded-for"] || req.socket.remoteAddress;
  const result = await validateLicense(req.body, clientIp);
  const statusCode = result.ok ? 200 : 403;
  res.status(statusCode).json(result);
});

/**
 * Public Endpoint: Hủy kích hoạt trên thiết bị (POST /deactivate-license hoặc /deactivateLicense)
 */
exports.deactivateLicense = onRequest(async (req, res) => {
  if (handleCors(req, res)) return;
  if (req.method !== "POST") {
    res.status(405).json({ ok: false, errorCode: "METHOD_NOT_ALLOWED", message: "Method Not Allowed" });
    return;
  }

  const clientIp = req.headers["x-forwarded-for"] || req.socket.remoteAddress;
  const result = await deactivateLicense(req.body, clientIp);
  const statusCode = result.ok ? 200 : 400;
  res.status(statusCode).json(result);
});

/**
 * Public Endpoint: Lấy Ed25519 Public Key
 */
exports.getPublicKey = onRequest((req, res) => {
  if (handleCors(req, res)) return;
  try {
    const pubHex = getEd25519PublicKeyHex();
    res.status(200).json({ ok: true, publicKeyHex: pubHex, algorithm: "Ed25519" });
  } catch (err) {
    res.status(500).json({ ok: false, message: err.message });
  }
});

/**
 * Admin API Gateway: Bảo vệ bằng X-Admin-Key
 */
exports.adminApi = onRequest(async (req, res) => {
  if (handleCors(req, res)) return;
  if (!verifyAdminAuth(req, res)) return;

  const action = (req.body && req.body.action) || (req.query && req.query.action);

  try {
    let result;
    switch (action) {
      case "create":
        result = await adminService.createLicense(req.body);
        break;
      case "block":
        result = await adminService.blockLicense(req.body.key, req.body.reason);
        break;
      case "unblock":
        result = await adminService.unblockLicense(req.body.key);
        break;
      case "extend":
        result = await adminService.extendLicense(req.body.key, req.body.days);
        break;
      case "revoke":
        result = await adminService.revokeActivation(req.body.key, req.body.machineId);
        break;
      case "list":
        result = await adminService.listActivations(req.body.key);
        break;
      default:
        res.status(400).json({ ok: false, message: `Unknown action: ${action}` });
        return;
    }
    res.status(200).json(result);
  } catch (err) {
    res.status(500).json({ ok: false, message: err.message });
  }
});
