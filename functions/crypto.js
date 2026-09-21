"use strict";

const crypto = require("crypto");

const KEY_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"; // Không chứa 0, O, 1, I để tránh nhầm lẫn

let cachedPrivateKeyPem = null;
let cachedPublicKeyHex = null;

/**
 * Sinh License Key chuẩn CSPRNG dạng VB-XXXX-XXXX-XXXX-XXXX-XXXX
 */
function generateLicenseKey() {
  const groups = [];
  for (let g = 0; g < 5; g++) {
    const bytes = crypto.randomBytes(4);
    let group = "";
    for (let i = 0; i < 4; i++) {
      group += KEY_ALPHABET[bytes[i] % KEY_ALPHABET.length];
    }
    groups.push(group);
  }
  return `VB-${groups.join("-")}`;
}

/**
 * Chuẩn hóa License Key: trim, viết hoa
 */
function normalizeLicenseKey(rawKey) {
  if (!rawKey || typeof rawKey !== "string") return "";
  return rawKey.trim().toUpperCase();
}

/**
 * SHA-256 Hash của License Key
 */
function hashLicenseKey(normalizedKey) {
  return crypto.createHash("sha256").update(normalizedKey, "utf8").digest("hex");
}

/**
 * SHA-256 Hash của Machine ID (bảo vệ phần cứng người dùng)
 */
function hashMachineId(machineId) {
  if (!machineId || typeof machineId !== "string") return "";
  const clean = machineId.trim().toUpperCase();
  return crypto.createHash("sha256").update(clean, "utf8").digest("hex");
}

/**
 * Lấy Private Key Ed25519 từ biến môi trường/secret hoặc sinh ephemeral key khi test/local emulator
 */
function getEd25519PrivateKeyPem() {
  if (cachedPrivateKeyPem) return cachedPrivateKeyPem;

  const envKey = process.env.ED25519_PRIVATE_KEY_PEM;
  if (envKey && envKey.includes("PRIVATE KEY")) {
    cachedPrivateKeyPem = envKey.replace(/\\n/g, "\n");
    return cachedPrivateKeyPem;
  }

  // Tự sinh key tạm khi chưa cấu hình secret
  const { privateKey, publicKey } = crypto.generateKeyPairSync("ed25519");
  cachedPrivateKeyPem = privateKey.export({ type: "pkcs8", format: "pem" }).toString();
  const pubRaw = publicKey.export({ type: "spki", format: "der" });
  cachedPublicKeyHex = pubRaw.subarray(pubRaw.length - 32).toString("hex");

  return cachedPrivateKeyPem;
}

/**
 * Lấy Public Key Ed25519 định dạng hex (32 bytes)
 */
function getEd25519PublicKeyHex() {
  if (cachedPublicKeyHex) return cachedPublicKeyHex;
  const pem = getEd25519PrivateKeyPem();
  const privKeyObj = crypto.createPrivateKey(pem);
  const pubKeyObj = crypto.createPublicKey(privKeyObj);
  const pubRaw = pubKeyObj.export({ type: "spki", format: "der" });
  cachedPublicKeyHex = pubRaw.subarray(pubRaw.length - 32).toString("hex");
  return cachedPublicKeyHex;
}

/**
 * Ký Ed25519 Signed Activation Token
 * Định dạng: base64url(payloadJson).base64url(sigBytes)
 */
function signActivationToken(payload, customPem) {
  const pem = customPem || getEd25519PrivateKeyPem();
  const privateKeyObj = crypto.createPrivateKey(pem);

  const payloadJson = JSON.stringify(payload);
  const payloadBytes = Buffer.from(payloadJson, "utf8");

  const signature = crypto.sign(null, payloadBytes, privateKeyObj);
  const payloadB64 = payloadBytes.toString("base64url");
  const sigB64 = signature.toString("base64url");

  return `${payloadB64}.${sigB64}`;
}

/**
 * Xác thực Ed25519 Token
 */
function verifyActivationToken(token, customPubKey) {
  try {
    if (!token || typeof token !== "string") {
      return { valid: false, error: "Empty token" };
    }
    const parts = token.split(".");
    if (parts.length !== 2) {
      return { valid: false, error: "Malformed token structure" };
    }

    const payloadBytes = Buffer.from(parts[0], "base64url");
    const sigBytes = Buffer.from(parts[1], "base64url");

    if (sigBytes.length !== 64) {
      return { valid: false, error: "Invalid Ed25519 signature length" };
    }

    let pubKeyObj;
    if (customPubKey) {
      pubKeyObj = typeof customPubKey === "string" ? crypto.createPublicKey(customPubKey) : customPubKey;
    } else {
      const privObj = crypto.createPrivateKey(getEd25519PrivateKeyPem());
      pubKeyObj = crypto.createPublicKey(privObj);
    }

    const verified = crypto.verify(null, payloadBytes, pubKeyObj, sigBytes);
    if (!verified) {
      return { valid: false, error: "Signature mismatch" };
    }

    const payload = JSON.parse(payloadBytes.toString("utf8"));
    return { valid: true, payload };
  } catch (err) {
    return { valid: false, error: err.message };
  }
}

module.exports = {
  generateLicenseKey,
  normalizeLicenseKey,
  hashLicenseKey,
  hashMachineId,
  getEd25519PrivateKeyPem,
  getEd25519PublicKeyHex,
  signActivationToken,
  verifyActivationToken,
};
