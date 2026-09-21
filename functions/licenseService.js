"use strict";

const admin = require("firebase-admin");
const {
  normalizeLicenseKey,
  hashLicenseKey,
  hashMachineId,
  signActivationToken,
  verifyActivationToken,
} = require("./crypto");

const DEFAULT_LEASE_SECONDS = 30 * 24 * 60 * 60; // 30 ngày lease offline

function db() {
  return admin.firestore();
}

function getActivationId(licenseHash, machineIdHash) {
  const crypto = require("crypto");
  return crypto.createHash("sha256").update(`${licenseHash}:${machineIdHash}`, "utf8").digest("hex");
}

/**
 * Xử lý kích hoạt License trực tuyến với Firestore Transaction
 */
async function activateLicense(reqBody, clientIp) {
  const rawKey = reqBody && reqBody.licenseKey;
  const machineId = reqBody && reqBody.machineId;

  if (!rawKey || typeof rawKey !== "string" || rawKey.trim().length < 10) {
    return {
      ok: false,
      errorCode: "LICENSE_INVALID",
      message: "Mã kích hoạt không đúng định dạng.",
    };
  }

  if (!machineId || typeof machineId !== "string" || machineId.trim().length < 8) {
    return {
      ok: false,
      errorCode: "LICENSE_INVALID",
      message: "Mã nhận diện máy tính (Machine ID) không hợp lệ.",
    };
  }

  const normalizedKey = normalizeLicenseKey(rawKey);
  const licenseHash = hashLicenseKey(normalizedKey);
  const machineIdHash = hashMachineId(machineId);
  const activationId = getActivationId(licenseHash, machineIdHash);

  const licenseRef = db().collection("licenses").doc(licenseHash);
  const activationRef = db().collection("activations").doc(activationId);
  const deviceRef = db().collection("devices").doc(machineIdHash);
  const auditLogRef = db().collection("auditLogs").doc();

  const nowSeconds = Math.floor(Date.now() / 1000);

  try {
    const result = await db().runTransaction(async (transaction) => {
      // 1. Thực hiện toàn bộ READS trước (bắt buộc trong Firestore transactions)
      const licenseSnap = await transaction.get(licenseRef);
      const activationSnap = await transaction.get(activationRef);
      const deviceSnap = await transaction.get(deviceRef);

      if (!licenseSnap.exists) {
        return { error: "LICENSE_INVALID", message: "Mã bản quyền không tồn tại." };
      }

      const licenseData = licenseSnap.data();

      // 2. Kiểm tra trạng thái License
      if (licenseData.status === "blocked") {
        return { error: "LICENSE_BLOCKED", message: "Mã bản quyền này đã bị khóa." };
      }
      if (licenseData.status === "expired") {
        return { error: "LICENSE_EXPIRED", message: "Mã bản quyền này đã hết hạn sử dụng." };
      }

      // 3. Kiểm tra ngày hết hạn
      if (licenseData.expiresAt) {
        const expiresAtMillis = licenseData.expiresAt.toMillis();
        if (Date.now() > expiresAtMillis) {
          transaction.update(licenseRef, { status: "expired" });
          return { error: "LICENSE_EXPIRED", message: "Mã bản quyền này đã hết hạn sử dụng." };
        }
      }

      // 4. Kiểm tra Activation hiện tại
      const isReactivation = activationSnap.exists && activationSnap.data().status === "active";

      let currentCount = licenseData.activationCount || 0;
      const maxDevices = licenseData.maxDevices || 1;

      if (!isReactivation) {
        if (currentCount >= maxDevices) {
          transaction.set(auditLogRef, {
            event: "DEVICE_LIMIT_EXCEEDED",
            licenseHash,
            machineIdHash,
            timestamp: admin.firestore.FieldValue.serverTimestamp(),
            metadata: {
              ip: clientIp || null,
              appVersion: reqBody.appVersion || null,
              maxDevices,
            },
          });
          return {
            error: "DEVICE_LIMIT_REACHED",
            message: `Mã bản quyền đã đạt số lượng thiết bị tối đa (${maxDevices} máy).`,
          };
        }

        currentCount += 1;
        transaction.update(licenseRef, { activationCount: currentCount });

        transaction.set(activationRef, {
          licenseHash,
          machineIdHash,
          status: "active",
          activatedAt: admin.firestore.FieldValue.serverTimestamp(),
          lastValidatedAt: admin.firestore.FieldValue.serverTimestamp(),
          revokedAt: null,
          tokenVersion: 2,
        });
      } else {
        transaction.update(activationRef, {
          lastValidatedAt: admin.firestore.FieldValue.serverTimestamp(),
        });
      }

      // 5. Cập nhật device
      if (!deviceSnap.exists) {
        transaction.set(deviceRef, {
          machineIdHash,
          firstSeenAt: admin.firestore.FieldValue.serverTimestamp(),
          lastSeenAt: admin.firestore.FieldValue.serverTimestamp(),
          status: "active",
        });
      } else {
        transaction.update(deviceRef, {
          lastSeenAt: admin.firestore.FieldValue.serverTimestamp(),
        });
      }

      // 5. Ghi Audit Log
      transaction.set(auditLogRef, {
        event: isReactivation ? "LICENSE_REACTIVATED" : "LICENSE_ACTIVATED",
        licenseHash,
        machineIdHash,
        timestamp: admin.firestore.FieldValue.serverTimestamp(),
        metadata: {
          ip: clientIp || null,
          appVersion: reqBody.appVersion || null,
          activationCount: currentCount,
        },
      });

      return { success: true, licenseData };
    });

    if (result.error) {
      return {
        ok: false,
        errorCode: result.error,
        message: result.message,
      };
    }

    const license = result.licenseData;
    const expiresAtSeconds = license.expiresAt ? Math.floor(license.expiresAt.toMillis() / 1000) : null;
    const validationUntilSeconds = nowSeconds + DEFAULT_LEASE_SECONDS;

    // Ký Ed25519 Token
    const tokenPayload = {
      v: 2,
      p: "voca-basic",
      lid: licenseHash,
      mid: machineIdHash,
      plan: license.plan || "lifetime",
      iat: nowSeconds,
      exp: expiresAtSeconds,
      val: validationUntilSeconds,
      cust: license.customerId || "Khách hàng",
    };

    const signedToken = signActivationToken(tokenPayload);

    return {
      ok: true,
      status: "active",
      activationToken: signedToken,
      plan: license.plan,
      expiresAt: license.expiresAt ? license.expiresAt.toDate().toISOString() : null,
      validationUntil: new Date(validationUntilSeconds * 1000).toISOString(),
      message: "Kích hoạt bản quyền thành công!",
    };
  } catch (err) {
    console.error("activateLicense error:", err);
    return {
      ok: false,
      errorCode: "SERVICE_UNAVAILABLE",
      message: "Lỗi hệ thống máy chủ bản quyền.",
    };
  }
}

/**
 * Xác thực & làm mới token định kỳ
 */
async function validateLicense(reqBody, clientIp) {
  const activationToken = reqBody && reqBody.activationToken;
  const machineId = reqBody && reqBody.machineId;

  if (!activationToken || !machineId) {
    return {
      ok: false,
      errorCode: "TOKEN_INVALID",
      message: "Thiếu activationToken hoặc machineId.",
    };
  }

  const tokenVerif = verifyActivationToken(activationToken);
  if (!tokenVerif.valid || !tokenVerif.payload) {
    return {
      ok: false,
      errorCode: "TOKEN_INVALID",
      message: "Token bản quyền không hợp lệ.",
    };
  }

  const tokenPayload = tokenVerif.payload;
  const machineIdHash = hashMachineId(machineId);

  if (tokenPayload.mid !== machineIdHash) {
    return {
      ok: false,
      errorCode: "MACHINE_MISMATCH",
      message: "Mã nhận diện máy tính không khớp với token bản quyền.",
    };
  }

  const licenseHash = tokenPayload.lid;
  const activationId = getActivationId(licenseHash, machineIdHash);

  try {
    const activationSnap = await db().collection("activations").doc(activationId).get();
    if (!activationSnap.exists || activationSnap.data().status !== "active") {
      return {
        ok: false,
        errorCode: "ACTIVATION_REVOKED",
        message: "Bản quyền trên thiết bị này đã bị thu hồi.",
      };
    }

    const licenseSnap = await db().collection("licenses").doc(licenseHash).get();
    if (!licenseSnap.exists) {
      return {
        ok: false,
        errorCode: "LICENSE_INVALID",
        message: "Mã bản quyền không còn tồn tại.",
      };
    }

    const licenseData = licenseSnap.data();
    if (licenseData.status === "blocked") {
      return {
        ok: false,
        errorCode: "LICENSE_BLOCKED",
        message: "Mã bản quyền đã bị khóa.",
      };
    }

    if (licenseData.expiresAt && Date.now() > licenseData.expiresAt.toMillis()) {
      return {
        ok: false,
        errorCode: "LICENSE_EXPIRED",
        message: "Bản quyền đã hết hạn sử dụng.",
      };
    }

    await db().collection("activations").doc(activationId).update({
      lastValidatedAt: admin.firestore.FieldValue.serverTimestamp(),
    });

    const nowSeconds = Math.floor(Date.now() / 1000);
    const expiresAtSeconds = licenseData.expiresAt ? Math.floor(licenseData.expiresAt.toMillis() / 1000) : null;
    const validationUntilSeconds = nowSeconds + DEFAULT_LEASE_SECONDS;

    const refreshedPayload = {
      v: 2,
      p: "voca-basic",
      lid: licenseHash,
      mid: machineIdHash,
      plan: licenseData.plan,
      iat: nowSeconds,
      exp: expiresAtSeconds,
      val: validationUntilSeconds,
      cust: licenseData.customerId,
    };

    const refreshedToken = signActivationToken(refreshedPayload);

    return {
      ok: true,
      status: "active",
      activationToken: refreshedToken,
      plan: licenseData.plan,
      expiresAt: licenseData.expiresAt ? licenseData.expiresAt.toDate().toISOString() : null,
      validationUntil: new Date(validationUntilSeconds * 1000).toISOString(),
      message: "Bản quyền hợp lệ và đã được làm mới.",
    };
  } catch (err) {
    console.error("validateLicense error:", err);
    return {
      ok: false,
      errorCode: "SERVICE_UNAVAILABLE",
      message: "Không thể kết nối máy chủ bản quyền.",
    };
  }
}

/**
 * Hủy kích hoạt bản quyền trên thiết bị
 */
async function deactivateLicense(reqBody, clientIp) {
  const activationToken = reqBody && reqBody.activationToken;
  const machineId = reqBody && reqBody.machineId;

  if (!activationToken || !machineId) {
    return {
      ok: false,
      errorCode: "TOKEN_INVALID",
      message: "Thiếu activationToken hoặc machineId.",
    };
  }

  const tokenVerif = verifyActivationToken(activationToken);
  if (!tokenVerif.valid || !tokenVerif.payload) {
    return {
      ok: false,
      errorCode: "TOKEN_INVALID",
      message: "Token bản quyền không hợp lệ.",
    };
  }

  const tokenPayload = tokenVerif.payload;
  const machineIdHash = hashMachineId(machineId);

  if (tokenPayload.mid !== machineIdHash) {
    return {
      ok: false,
      errorCode: "MACHINE_MISMATCH",
      message: "Mã nhận diện máy tính không khớp.",
    };
  }

  const licenseHash = tokenPayload.lid;
  const activationId = getActivationId(licenseHash, machineIdHash);

  const licenseRef = db().collection("licenses").doc(licenseHash);
  const activationRef = db().collection("activations").doc(activationId);
  const auditLogRef = db().collection("auditLogs").doc();

  try {
    await db().runTransaction(async (transaction) => {
      const activationSnap = await transaction.get(activationRef);
      const licenseSnap = await transaction.get(licenseRef);

      if (!activationSnap.exists || activationSnap.data().status !== "active") {
        return;
      }

      transaction.update(activationRef, {
        status: "revoked",
        revokedAt: admin.firestore.FieldValue.serverTimestamp(),
      });

      if (licenseSnap.exists) {
        const count = licenseSnap.data().activationCount || 0;
        transaction.update(licenseRef, {
          activationCount: Math.max(0, count - 1),
        });
      }

      transaction.set(auditLogRef, {
        event: "LICENSE_DEACTIVATED",
        licenseHash,
        machineIdHash,
        timestamp: admin.firestore.FieldValue.serverTimestamp(),
        metadata: { ip: clientIp || null },
      });
    });

    return {
      ok: true,
      message: "Hủy kích hoạt bản quyền thành công.",
    };
  } catch (err) {
    console.error("deactivateLicense error:", err);
    return {
      ok: false,
      errorCode: "SERVICE_UNAVAILABLE",
      message: "Lỗi khi hủy kích hoạt bản quyền.",
    };
  }
}

module.exports = {
  activateLicense,
  validateLicense,
  deactivateLicense,
  getActivationId,
};
