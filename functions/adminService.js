"use strict";

const admin = require("firebase-admin");
const {
  generateLicenseKey,
  normalizeLicenseKey,
  hashLicenseKey,
  hashMachineId,
} = require("./crypto");
const { getActivationId } = require("./licenseService");

function db() {
  return admin.firestore();
}

/**
 * Admin: Tạo License mới với CSPRNG key
 */
async function createLicense(reqBody) {
  const plan = reqBody && reqBody.plan === "time_limited" ? "time_limited" : "lifetime";
  const maxDevices = Math.max(1, (reqBody && reqBody.maxDevices) || 1);
  const customerId = ((reqBody && reqBody.customerId) || "Khách hàng").trim();

  const rawKey = generateLicenseKey();
  const normalizedKey = normalizeLicenseKey(rawKey);
  const licenseHash = hashLicenseKey(normalizedKey);

  let expiresAt = null;
  if (plan === "time_limited") {
    const days = Math.max(1, (reqBody && reqBody.days) || 30);
    const expireDate = new Date(Date.now() + days * 24 * 60 * 60 * 1000);
    expiresAt = admin.firestore.Timestamp.fromDate(expireDate);
  }

  const licenseDoc = {
    status: "active",
    plan,
    maxDevices,
    activationCount: 0,
    customerId,
    createdAt: admin.firestore.FieldValue.serverTimestamp(),
    expiresAt,
    metadata: {
      product: "voca-basic",
      version: 2,
      notes: (reqBody && reqBody.notes) || "",
    },
  };

  await db().collection("licenses").doc(licenseHash).set(licenseDoc);

  await db().collection("auditLogs").add({
    event: "LICENSE_CREATED",
    licenseHash,
    timestamp: admin.firestore.FieldValue.serverTimestamp(),
    metadata: { plan, maxDevices, customerId },
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
 * Admin: Khóa License
 */
async function blockLicense(licenseKeyOrHash, reason) {
  const clean = String(licenseKeyOrHash).trim();
  const licenseHash = clean.startsWith("VB-") ? hashLicenseKey(normalizeLicenseKey(clean)) : clean;

  const licenseRef = db().collection("licenses").doc(licenseHash);
  const snap = await licenseRef.get();
  if (!snap.exists) {
    return { ok: false, errorCode: "LICENSE_INVALID", message: "Không tìm thấy license." };
  }

  await licenseRef.update({
    status: "blocked",
    "metadata.blockedReason": reason || "Admin blocked",
    "metadata.blockedAt": admin.firestore.FieldValue.serverTimestamp(),
  });

  await db().collection("auditLogs").add({
    event: "LICENSE_BLOCKED",
    licenseHash,
    timestamp: admin.firestore.FieldValue.serverTimestamp(),
    metadata: { reason },
  });

  return { ok: true, licenseHash, status: "blocked" };
}

/**
 * Admin: Mở khóa License
 */
async function unblockLicense(licenseKeyOrHash) {
  const clean = String(licenseKeyOrHash).trim();
  const licenseHash = clean.startsWith("VB-") ? hashLicenseKey(normalizeLicenseKey(clean)) : clean;

  const licenseRef = db().collection("licenses").doc(licenseHash);
  const snap = await licenseRef.get();
  if (!snap.exists) {
    return { ok: false, errorCode: "LICENSE_INVALID", message: "Không tìm thấy license." };
  }

  await licenseRef.update({
    status: "active",
    "metadata.unblockedAt": admin.firestore.FieldValue.serverTimestamp(),
  });

  await db().collection("auditLogs").add({
    event: "LICENSE_UNBLOCKED",
    licenseHash,
    timestamp: admin.firestore.FieldValue.serverTimestamp(),
  });

  return { ok: true, licenseHash, status: "active" };
}

/**
 * Admin: Gia hạn License
 */
async function extendLicense(licenseKeyOrHash, additionalDays) {
  const clean = String(licenseKeyOrHash).trim();
  const licenseHash = clean.startsWith("VB-") ? hashLicenseKey(normalizeLicenseKey(clean)) : clean;

  const licenseRef = db().collection("licenses").doc(licenseHash);
  const snap = await licenseRef.get();
  if (!snap.exists) {
    return { ok: false, errorCode: "LICENSE_INVALID", message: "Không tìm thấy license." };
  }

  const data = snap.data();
  const currentExpiry = data.expiresAt ? data.expiresAt.toMillis() : Date.now();
  const newExpiry = new Date(Math.max(Date.now(), currentExpiry) + Number(additionalDays) * 24 * 60 * 60 * 1000);
  const newTimestamp = admin.firestore.Timestamp.fromDate(newExpiry);

  await licenseRef.update({
    status: "active",
    expiresAt: newTimestamp,
    plan: "time_limited",
  });

  await db().collection("auditLogs").add({
    event: "LICENSE_EXTENDED",
    licenseHash,
    timestamp: admin.firestore.FieldValue.serverTimestamp(),
    metadata: { additionalDays, newExpiresAt: newExpiry.toISOString() },
  });

  return { ok: true, licenseHash, newExpiresAt: newExpiry.toISOString() };
}

/**
 * Admin: Thu hồi kích hoạt thiết bị (Revoke / Device Reset)
 */
async function revokeActivation(licenseKeyOrHash, machineId) {
  const clean = String(licenseKeyOrHash).trim();
  const licenseHash = clean.startsWith("VB-") ? hashLicenseKey(normalizeLicenseKey(clean)) : clean;
  const machineIdHash = hashMachineId(machineId);
  const activationId = getActivationId(licenseHash, machineIdHash);

  const licenseRef = db().collection("licenses").doc(licenseHash);
  const activationRef = db().collection("activations").doc(activationId);

  await db().runTransaction(async (transaction) => {
    const actSnap = await transaction.get(activationRef);
    const licSnap = await transaction.get(licenseRef);

    if (!actSnap.exists || actSnap.data().status !== "active") {
      return;
    }

    transaction.update(activationRef, {
      status: "revoked",
      revokedAt: admin.firestore.FieldValue.serverTimestamp(),
    });

    if (licSnap.exists) {
      const count = licSnap.data().activationCount || 0;
      transaction.update(licenseRef, {
        activationCount: Math.max(0, count - 1),
      });
    }

    transaction.set(db().collection("auditLogs").doc(), {
      event: "LICENSE_REVOKED",
      licenseHash,
      machineIdHash,
      timestamp: admin.firestore.FieldValue.serverTimestamp(),
      metadata: { adminAction: true },
    });
  });

  return { ok: true, licenseHash, machineIdHash, status: "revoked" };
}

/**
 * Admin: Liệt kê các activation của 1 license
 */
async function listActivations(licenseKeyOrHash) {
  const clean = String(licenseKeyOrHash).trim();
  const licenseHash = clean.startsWith("VB-") ? hashLicenseKey(normalizeLicenseKey(clean)) : clean;

  const snaps = await db().collection("activations").where("licenseHash", "==", licenseHash).get();
  const activations = [];
  snaps.forEach((doc) => {
    activations.push({ id: doc.id, ...doc.data() });
  });

  return { ok: true, licenseHash, activations };
}

module.exports = {
  createLicense,
  blockLicense,
  unblockLicense,
  extendLicense,
  revokeActivation,
  listActivations,
};
