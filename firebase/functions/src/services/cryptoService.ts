import * as crypto from 'crypto';
import { getEd25519PrivateKeyPem } from '../config';
import { SignedTokenPayload } from '../types';

const KEY_ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'; // Không chứa 0, O, 1, I để tránh nhầm lẫn

/**
 * Sinh License Key chuẩn CSPRNG: VB-XXXX-XXXX-XXXX-XXXX-XXXX
 */
export function generateLicenseKey(): string {
  const groups: string[] = [];
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
export function normalizeLicenseKey(rawKey: string): string {
  if (!rawKey || typeof rawKey !== 'string') {
    return '';
  }
  return rawKey.trim().toUpperCase();
}

/**
 * SHA-256 Hash của License Key đã chuẩn hóa
 */
export function hashLicenseKey(normalizedKey: string): string {
  return crypto.createHash('sha256').update(normalizedKey, 'utf8').digest('hex');
}

/**
 * SHA-256 Hash của Machine ID (bảo vệ thông tin phần cứng người dùng)
 */
export function hashMachineId(machineId: string): string {
  if (!machineId || typeof machineId !== 'string') {
    return '';
  }
  const clean = machineId.trim().toUpperCase();
  return crypto.createHash('sha256').update(clean, 'utf8').digest('hex');
}

/**
 * Base64URL encode buffer/string
 */
export function base64urlEncode(data: Buffer | string): string {
  const buf = Buffer.isBuffer(data) ? data : Buffer.from(data, 'utf8');
  return buf.toString('base64url');
}

/**
 * Base64URL decode to string
 */
export function base64urlDecode(str: string): Buffer {
  return Buffer.from(str, 'base64url');
}

/**
 * Ký Signed Activation Token sử dụng Ed25519 Private Key
 * Token format: base64url(payload_json).base64url(signature_bytes)
 */
export function signActivationToken(
  payload: SignedTokenPayload,
  customPrivateKeyPem?: string
): string {
  const pem = customPrivateKeyPem || getEd25519PrivateKeyPem();
  const privateKeyObj = crypto.createPrivateKey(pem);

  const payloadJson = JSON.stringify(payload);
  const payloadBytes = Buffer.from(payloadJson, 'utf8');

  const signature = crypto.sign(null, payloadBytes, privateKeyObj);

  return `${base64urlEncode(payloadBytes)}.${base64urlEncode(signature)}`;
}

/**
 * Xác thực Signed Activation Token bằng Ed25519 Public Key
 */
export function verifyActivationToken(
  token: string,
  publicKeyPemOrDer?: crypto.KeyLike
): { valid: boolean; payload: SignedTokenPayload | null; error?: string } {
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
    let pubKeyObj: crypto.KeyObject;
    if (publicKeyPemOrDer) {
      pubKeyObj = typeof publicKeyPemOrDer === 'string'
        ? crypto.createPublicKey(publicKeyPemOrDer)
        : (publicKeyPemOrDer as crypto.KeyObject);
    } else {
      const privObj = crypto.createPrivateKey(getEd25519PrivateKeyPem());
      pubKeyObj = crypto.createPublicKey(privObj);
    }

    const isVerified = crypto.verify(null, payloadBytes, pubKeyObj, sigBytes);
    if (!isVerified) {
      return { valid: false, payload: null, error: 'Signature mismatch' };
    }

    const payload = JSON.parse(payloadBytes.toString('utf8')) as SignedTokenPayload;
    return { valid: true, payload };
  } catch (err: any) {
    return { valid: false, payload: null, error: err.message || 'Token verification failed' };
  }
}
