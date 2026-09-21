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
exports.DEFAULT_LEASE_SECONDS = void 0;
exports.getEd25519PrivateKeyPem = getEd25519PrivateKeyPem;
exports.getEd25519PublicKeyHex = getEd25519PublicKeyHex;
exports.getAdminApiKey = getAdminApiKey;
const crypto = __importStar(require("crypto"));
// 30 ngày lease offline mặc định
exports.DEFAULT_LEASE_SECONDS = 30 * 24 * 60 * 60;
/**
 * Lấy Private Key Ed25519 phục vụ việc ký Activation Token.
 * Ưu tiên:
 * 1. process.env.ED25519_PRIVATE_KEY_PEM (hoặc Firebase Secret)
 * 2. Tự động sinh key ngẫu nhiên trong môi trường test/local emulator nếu chưa cấu hình secret.
 */
let cachedPrivateKeyPem = null;
let cachedPublicKeyHex = null;
function getEd25519PrivateKeyPem() {
    if (cachedPrivateKeyPem) {
        return cachedPrivateKeyPem;
    }
    const envKey = process.env.ED25519_PRIVATE_KEY_PEM;
    if (envKey && envKey.includes('PRIVATE KEY')) {
        cachedPrivateKeyPem = envKey.replace(/\\n/g, '\n');
        return cachedPrivateKeyPem;
    }
    // Nếu là môi trường dev/emulator chưa set secret, tự sinh một cặp khóa Ed25519 tạm
    console.warn('[WARN] ED25519_PRIVATE_KEY_PEM is not set. Generating an ephemeral Ed25519 keypair for local execution.');
    const { privateKey, publicKey } = crypto.generateKeyPairSync('ed25519');
    cachedPrivateKeyPem = privateKey.export({ type: 'pkcs8', format: 'pem' }).toString();
    const pubRaw = publicKey.export({ type: 'spki', format: 'der' });
    // In DER format for Ed25519 SPKI, the raw 32-byte public key is the last 32 bytes
    cachedPublicKeyHex = pubRaw.subarray(pubRaw.length - 32).toString('hex');
    console.info(`[INFO] Ephemeral Public Key (Hex): ${cachedPublicKeyHex}`);
    return cachedPrivateKeyPem;
}
function getEd25519PublicKeyHex() {
    if (cachedPublicKeyHex) {
        return cachedPublicKeyHex;
    }
    const pem = getEd25519PrivateKeyPem();
    const privKeyObj = crypto.createPrivateKey(pem);
    const pubKeyObj = crypto.createPublicKey(privKeyObj);
    const pubRaw = pubKeyObj.export({ type: 'spki', format: 'der' });
    cachedPublicKeyHex = pubRaw.subarray(pubRaw.length - 32).toString('hex');
    return cachedPublicKeyHex;
}
function getAdminApiKey() {
    return process.env.ADMIN_API_KEY || 'voca-basic-default-admin-secret-change-in-production';
}
//# sourceMappingURL=config.js.map