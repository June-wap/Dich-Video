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
exports.generateLicenseKey = generateLicenseKey;
exports.normalizeLicenseKey = normalizeLicenseKey;
exports.hashLicenseKey = hashLicenseKey;
exports.hashMachineId = hashMachineId;
exports.base64urlEncode = base64urlEncode;
exports.base64urlDecode = base64urlDecode;
exports.signActivationToken = signActivationToken;
exports.verifyActivationToken = verifyActivationToken;
const crypto = __importStar(require("crypto"));
const config_1 = require("../config");
const KEY_ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'; // Không chứa 0, O, 1, I để tránh nhầm lẫn
/**
 * Sinh License Key chuẩn CSPRNG: VB-XXXX-XXXX-XXXX-XXXX-XXXX
 */
function generateLicenseKey() {
    const groups = [];
    for (let g = 0; g < 5; g++) {
        const bytes = crypto.randomBytes(4);
        let group = '';
        for (let i = 0; i < 4; i++) {
            group += KEY_ALPHABET[bytes[i] % KEY_ALPHABET.length];
        }
        groups.push(group);
    }
    return `VB-${groups.join('-')}`;
}
/**
 * Chuẩn hóa License Key: trim, viết hoa, format canonical
 */
function normalizeLicenseKey(rawKey) {
    if (!rawKey || typeof rawKey !== 'string') {
        return '';
    }
    return rawKey.trim().toUpperCase();
}
/**
 * SHA-256 Hash của License Key đã chuẩn hóa
 */
function hashLicenseKey(normalizedKey) {
    return crypto.createHash('sha256').update(normalizedKey, 'utf8').digest('hex');
}
/**
 * SHA-256 Hash của Machine ID (bảo vệ thông tin phần cứng người dùng)
 */
function hashMachineId(machineId) {
    if (!machineId || typeof machineId !== 'string') {
        return '';
    }
    const clean = machineId.trim().toUpperCase();
    return crypto.createHash('sha256').update(clean, 'utf8').digest('hex');
}
/**
 * Base64URL encode buffer/string
 */
function base64urlEncode(data) {
    const buf = Buffer.isBuffer(data) ? data : Buffer.from(data, 'utf8');
    return buf.toString('base64url');
}
/**
 * Base64URL decode to string
 */
function base64urlDecode(str) {
    return Buffer.from(str, 'base64url');
}
/**
 * Ký Signed Activation Token sử dụng Ed25519 Private Key
 * Token format: base64url(payload_json).base64url(signature_bytes)
 */
function signActivationToken(payload, customPrivateKeyPem) {
    const pem = customPrivateKeyPem || (0, config_1.getEd25519PrivateKeyPem)();
    const privateKeyObj = crypto.createPrivateKey(pem);
    const payloadJson = JSON.stringify(payload);
    const payloadBytes = Buffer.from(payloadJson, 'utf8');
    const signature = crypto.sign(null, payloadBytes, privateKeyObj);
    return `${base64urlEncode(payloadBytes)}.${base64urlEncode(signature)}`;
}
/**
 * Xác thực Signed Activation Token bằng Ed25519 Public Key
 */
function verifyActivationToken(token, publicKeyPemOrDer) {
    try {
        const parts = token.split('.');
        if (parts.length !== 2) {
            return { valid: false, payload: null, error: 'Malformed token structure' };
        }
        const payloadBytes = base64urlDecode(parts[0]);
        const sigBytes = base64urlDecode(parts[1]);
        if (sigBytes.length !== 64) {
            return { valid: false, payload: null, error: 'Invalid signature length for Ed25519' };
        }
        // Nếu không truyền public key thì trích xuất từ private key hiện tại (server-side verify)
        let pubKeyObj;
        if (publicKeyPemOrDer) {
            pubKeyObj = typeof publicKeyPemOrDer === 'string'
                ? crypto.createPublicKey(publicKeyPemOrDer)
                : publicKeyPemOrDer;
        }
        else {
            const privObj = crypto.createPrivateKey((0, config_1.getEd25519PrivateKeyPem)());
            pubKeyObj = crypto.createPublicKey(privObj);
        }
        const isVerified = crypto.verify(null, payloadBytes, pubKeyObj, sigBytes);
        if (!isVerified) {
            return { valid: false, payload: null, error: 'Signature mismatch' };
        }
        const payload = JSON.parse(payloadBytes.toString('utf8'));
        return { valid: true, payload };
    }
    catch (err) {
        return { valid: false, payload: null, error: err.message || 'Token verification failed' };
    }
}
//# sourceMappingURL=cryptoService.js.map