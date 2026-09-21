import * as crypto from 'crypto';

export interface AppConfig {
  defaultLeaseDurationSeconds: number; // Mặc định 30 ngày
  privateKeyPem: string;
  adminApiKey: string;
}

// 30 ngày lease offline mặc định
export const DEFAULT_LEASE_SECONDS = 30 * 24 * 60 * 60;

/**
 * Lấy Private Key Ed25519 phục vụ việc ký Activation Token.
 * Ưu tiên:
 * 1. process.env.ED25519_PRIVATE_KEY_PEM (hoặc Firebase Secret)
 * 2. Tự động sinh key ngẫu nhiên trong môi trường test/local emulator nếu chưa cấu hình secret.
 */
let cachedPrivateKeyPem: string | null = null;
let cachedPublicKeyHex: string | null = null;

export function getEd25519PrivateKeyPem(): string {
  if (cachedPrivateKeyPem) {
    return cachedPrivateKeyPem;
  }

  const envKey = process.env.ED25519_PRIVATE_KEY_PEM;
  if (envKey && envKey.includes('PRIVATE KEY')) {
    cachedPrivateKeyPem = envKey.replace(/\\n/g, '\n');
    return cachedPrivateKeyPem;
  }

  // Nếu là môi trường dev/emulator chưa set secret, tự sinh một cặp khóa Ed25519 tạm
  console.warn(
    '[WARN] ED25519_PRIVATE_KEY_PEM is not set. Generating an ephemeral Ed25519 keypair for local execution.'
  );
  const { privateKey, publicKey } = crypto.generateKeyPairSync('ed25519');
  cachedPrivateKeyPem = privateKey.export({ type: 'pkcs8', format: 'pem' }).toString();
  const pubRaw = publicKey.export({ type: 'spki', format: 'der' });
  // In DER format for Ed25519 SPKI, the raw 32-byte public key is the last 32 bytes
  cachedPublicKeyHex = pubRaw.subarray(pubRaw.length - 32).toString('hex');
  console.info(`[INFO] Ephemeral Public Key (Hex): ${cachedPublicKeyHex}`);

  return cachedPrivateKeyPem;
}

export function getEd25519PublicKeyHex(): string {
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

export function getAdminApiKey(): string {
  return process.env.ADMIN_API_KEY || 'voca-basic-default-admin-secret-change-in-production';
}
