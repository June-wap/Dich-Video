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
const node_test_1 = require("node:test");
const assert = __importStar(require("node:assert"));
const cryptoService_1 = require("../services/cryptoService");
(0, node_test_1.describe)('Cloud License V2 - Cryptographic Services', () => {
    (0, node_test_1.it)('should generate CSPRNG license key matching format VB-XXXX-XXXX-XXXX-XXXX-XXXX', () => {
        const key = (0, cryptoService_1.generateLicenseKey)();
        assert.match(key, /^VB-[A-Z2-9]{4}-[A-Z2-9]{4}-[A-Z2-9]{4}-[A-Z2-9]{4}-[A-Z2-9]{4}$/);
    });
    (0, node_test_1.it)('should generate distinct keys consecutively (CSPRNG randomness)', () => {
        const key1 = (0, cryptoService_1.generateLicenseKey)();
        const key2 = (0, cryptoService_1.generateLicenseKey)();
        assert.notStrictEqual(key1, key2);
    });
    (0, node_test_1.it)('should normalize license key properly', () => {
        const raw = '  vb-abcd-efgh-1234-5678-9999 \t\n';
        const norm = (0, cryptoService_1.normalizeLicenseKey)(raw);
        assert.strictEqual(norm, 'VB-ABCD-EFGH-1234-5678-9999');
    });
    (0, node_test_1.it)('should hash license key with consistent SHA-256', () => {
        const key = 'VB-AAAA-BBBB-CCCC-DDDD-EEEE';
        const h1 = (0, cryptoService_1.hashLicenseKey)(key);
        const h2 = (0, cryptoService_1.hashLicenseKey)(key);
        assert.strictEqual(h1.length, 64);
        assert.strictEqual(h1, h2);
    });
    (0, node_test_1.it)('should hash machine id consistently without exposing raw value', () => {
        const mid = 'VB-78BC-1320-F15A-46DB';
        const h1 = (0, cryptoService_1.hashMachineId)(mid);
        const h2 = (0, cryptoService_1.hashMachineId)('  vb-78bc-1320-f15a-46db ');
        assert.strictEqual(h1, h2);
        assert.strictEqual(h1.length, 64);
    });
    (0, node_test_1.it)('should sign and verify valid Ed25519 token payload', () => {
        const mid = 'VB-78BC-1320-F15A-46DB';
        const midHash = (0, cryptoService_1.hashMachineId)(mid);
        const payload = {
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
        const token = (0, cryptoService_1.signActivationToken)(payload);
        assert.ok(token.includes('.'));
        const res = (0, cryptoService_1.verifyActivationToken)(token);
        assert.strictEqual(res.valid, true);
        assert.ok(res.payload);
        assert.strictEqual(res.payload.v, 2);
        assert.strictEqual(res.payload.mid, midHash);
        assert.strictEqual(res.payload.plan, 'lifetime');
        assert.strictEqual(res.payload.cust, 'Nguyen Van A');
    });
    (0, node_test_1.it)('should reject tampered Ed25519 token', () => {
        const payload = {
            v: 2,
            p: 'voca-basic',
            lid: 'lic-123',
            mid: 'mach-123',
            plan: 'lifetime',
            iat: 1000,
            exp: null,
            val: 2000,
        };
        const token = (0, cryptoService_1.signActivationToken)(payload);
        const parts = token.split('.');
        // Tamper payload
        const tamperedPayload = parts[0].slice(0, -4) + 'ZZZZ';
        const tamperedToken = `${tamperedPayload}.${parts[1]}`;
        const res = (0, cryptoService_1.verifyActivationToken)(tamperedToken);
        assert.strictEqual(res.valid, false);
        assert.strictEqual(res.payload, null);
        // Tamper signature
        const tamperedSig = parts[1].slice(0, -4) + 'AAAA';
        const tamperedSigToken = `${parts[0]}.${tamperedSig}`;
        const resSig = (0, cryptoService_1.verifyActivationToken)(tamperedSigToken);
        assert.strictEqual(resSig.valid, false);
    });
});
//# sourceMappingURL=crypto.test.js.map