import { describe, it } from 'node:test';
import * as assert from 'node:assert';
import {
  generateLicenseKey,
  normalizeLicenseKey,
  hashLicenseKey,
  hashMachineId,
  signActivationToken,
  verifyActivationToken,
} from '../services/cryptoService';
import { SignedTokenPayload } from '../types';

describe('Cloud License V2 - Cryptographic Services', () => {
  it('should generate CSPRNG license key matching format VB-XXXX-XXXX-XXXX-XXXX-XXXX', () => {
    const key = generateLicenseKey();
    assert.match(key, /^VB-[A-Z2-9]{4}-[A-Z2-9]{4}-[A-Z2-9]{4}-[A-Z2-9]{4}-[A-Z2-9]{4}$/);
  });

  it('should generate distinct keys consecutively (CSPRNG randomness)', () => {
    const key1 = generateLicenseKey();
    const key2 = generateLicenseKey();
    assert.notStrictEqual(key1, key2);
  });

  it('should normalize license key properly', () => {
    const raw = '  vb-abcd-efgh-1234-5678-9999 \t\n';
    const norm = normalizeLicenseKey(raw);
    assert.strictEqual(norm, 'VB-ABCD-EFGH-1234-5678-9999');
  });

  it('should hash license key with consistent SHA-256', () => {
    const key = 'VB-AAAA-BBBB-CCCC-DDDD-EEEE';
    const h1 = hashLicenseKey(key);
    const h2 = hashLicenseKey(key);
    assert.strictEqual(h1.length, 64);
    assert.strictEqual(h1, h2);
  });

  it('should hash machine id consistently without exposing raw value', () => {
    const mid = 'VB-78BC-1320-F15A-46DB';
    const h1 = hashMachineId(mid);
    const h2 = hashMachineId('  vb-78bc-1320-f15a-46db ');
    assert.strictEqual(h1, h2);
    assert.strictEqual(h1.length, 64);
  });

  it('should sign and verify valid Ed25519 token payload', () => {
    const mid = 'VB-78BC-1320-F15A-46DB';
    const midHash = hashMachineId(mid);
    const payload: SignedTokenPayload = {
      v: 2,
      p: 'voca-basic',
      lid: 'test-license-hash-12345678',
      mid: midHash,
      plan: 'lifetime',
      iat: Math.floor(Date.now() / 1000),
      exp: null,
      val: Math.floor(Date.now() / 1000) + 30 * 86400,
      cust: 'Nguyen Van A',
    };

    const token = signActivationToken(payload);
    assert.ok(token.includes('.'));

    const res = verifyActivationToken(token);
    assert.strictEqual(res.valid, true);
    assert.ok(res.payload);
    assert.strictEqual(res.payload.v, 2);
    assert.strictEqual(res.payload.mid, midHash);
    assert.strictEqual(res.payload.plan, 'lifetime');
    assert.strictEqual(res.payload.cust, 'Nguyen Van A');
  });

  it('should reject tampered Ed25519 token', () => {
    const payload: SignedTokenPayload = {
      v: 2,
      p: 'voca-basic',
      lid: 'lic-123',
      mid: 'mach-123',
      plan: 'lifetime',
      iat: 1000,
      exp: null,
      val: 2000,
    };
    const token = signActivationToken(payload);
    const parts = token.split('.');

    // Tamper payload
    const tamperedPayload = parts[0].slice(0, -4) + 'ZZZZ';
    const tamperedToken = `${tamperedPayload}.${parts[1]}`;

    const res = verifyActivationToken(tamperedToken);
    assert.strictEqual(res.valid, false);
    assert.strictEqual(res.payload, null);

    // Tamper signature
    const tamperedSig = parts[1].slice(0, -4) + 'AAAA';
    const tamperedSigToken = `${parts[0]}.${tamperedSig}`;
    const resSig = verifyActivationToken(tamperedSigToken);
    assert.strictEqual(resSig.valid, false);
  });
});
