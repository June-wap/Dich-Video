"use strict";

const { describe, it } = require("node:test");
const assert = require("node:assert");
const admin = require("firebase-admin");

const {
  generateLicenseKey,
  normalizeLicenseKey,
  hashLicenseKey,
  hashMachineId,
  signActivationToken,
  verifyActivationToken,
} = require("../crypto");

const {
  activateLicense,
  validateLicense,
  deactivateLicense,
} = require("../licenseService");

const {
  createLicense,
  blockLicense,
  unblockLicense,
} = require("../adminService");

// Nếu chạy với Firestore Emulator (FIRESTORE_EMULATOR_HOST), test sẽ thực hiện trên emulator thật
if (!admin.apps.length) {
  admin.initializeApp({ projectId: "vocaltts" });
}

describe("Firebase Cloud License V2 - Comprehensive Test Suite", () => {
  const machineA = "VB-52DB-86C8-DF9E-0C7E";
  const machineB = "VB-1111-2222-3333-4444";
  const machineC = "VB-AAAA-BBBB-CCCC-DDDD";

  describe("1. Cryptographic & Key Format Assertions", () => {
    it("1.1 should generate CSPRNG key matching format VB-XXXX-XXXX-XXXX-XXXX-XXXX", () => {
      const key = generateLicenseKey();
      assert.match(key, /^VB-[A-Z2-9]{4}-[A-Z2-9]{4}-[A-Z2-9]{4}-[A-Z2-9]{4}-[A-Z2-9]{4}$/);
    });

    it("1.2 should normalize key properly (trim, uppercase)", () => {
      const raw = "  vb-abcd-efgh-1234-5678-9999  ";
      assert.strictEqual(normalizeLicenseKey(raw), "VB-ABCD-EFGH-1234-5678-9999");
    });

    it("1.3 should compute deterministic SHA-256 for key and machine id", () => {
      const k = "VB-ABCD-EFGH-1234-5678-9999";
      const h1 = hashLicenseKey(k);
      const h2 = hashLicenseKey(k);
      assert.strictEqual(h1, h2);
      assert.strictEqual(h1.length, 64);

      const mHash = hashMachineId(machineA);
      assert.strictEqual(mHash.length, 64);
    });

    it("1.4 should sign and verify Ed25519 token", () => {
      const payload = {
        v: 2,
        p: "voca-basic",
        lid: "lic-hash-123",
        mid: hashMachineId(machineA),
        plan: "lifetime",
        iat: 1000,
        exp: null,
        val: 2000,
        cust: "Customer Test",
      };
      const token = signActivationToken(payload);
      assert.ok(token.includes("."));

      const res = verifyActivationToken(token);
      assert.strictEqual(res.valid, true);
      assert.strictEqual(res.payload.mid, hashMachineId(machineA));
    });

    it("1.5 should reject tampered Ed25519 token", () => {
      const payload = { v: 2, p: "voca-basic", lid: "123", mid: "456", plan: "lifetime" };
      const token = signActivationToken(payload);
      const parts = token.split(".");
      const tamperedPayload = parts[0].slice(0, -4) + "ZZZZ";
      const tamperedToken = `${tamperedPayload}.${parts[1]}`;

      const res = verifyActivationToken(tamperedToken);
      assert.strictEqual(res.valid, false);
    });

    it("1.6 should detect machine mismatch in token payload", () => {
      const payload = {
        v: 2,
        p: "voca-basic",
        lid: "lic-123",
        mid: hashMachineId(machineA),
        plan: "lifetime",
      };
      const token = signActivationToken(payload);
      const res = verifyActivationToken(token);
      assert.strictEqual(res.valid, true);

      // Verify mid does not match machineB
      assert.notStrictEqual(res.payload.mid, hashMachineId(machineB));
    });
  });

  describe("2. End-to-End Firestore & Service Operations", () => {
    let testLifetimeKey;
    let testTokenMachineA;

    it("2.1 Admin: create lifetime license", async () => {
      try {
        const res = await createLicense({
          customerId: "Cong ty ABC",
          plan: "lifetime",
          maxDevices: 2,
        });
        assert.strictEqual(res.ok, true);
        assert.ok(res.licenseKey.startsWith("VB-"));
        assert.strictEqual(res.maxDevices, 2);
        testLifetimeKey = res.licenseKey;
      } catch (err) {
        if (err.message.includes("Could not load the default credentials") || err.message.includes("ECONNREFUSED")) {
          // Khi chưa bật emulator hoặc chưa có credentials, bỏ qua bước gọi Firestore trực tiếp
          console.warn("[SKIP] Firestore not available for live transaction test");
          return;
        }
        throw err;
      }
    });

    it("2.2 Activation: valid license on machine A", async () => {
      if (!testLifetimeKey) return;
      const res = await activateLicense({
        licenseKey: testLifetimeKey,
        machineId: machineA,
        appVersion: "1.0.1",
      });
      assert.strictEqual(res.ok, true);
      assert.strictEqual(res.status, "active");
      assert.ok(res.activationToken);
      testTokenMachineA = res.activationToken;

      const verified = verifyActivationToken(res.activationToken);
      assert.strictEqual(verified.valid, true);
      assert.strictEqual(verified.payload.mid, hashMachineId(machineA));
    });

    it("2.3 Activation: same machine reactivation (idempotent)", async () => {
      if (!testLifetimeKey) return;
      const res = await activateLicense({
        licenseKey: testLifetimeKey,
        machineId: machineA,
      });
      assert.strictEqual(res.ok, true);
      assert.strictEqual(res.status, "active");
    });

    it("2.4 Activation: second machine within maxDevices=2", async () => {
      if (!testLifetimeKey) return;
      const res = await activateLicense({
        licenseKey: testLifetimeKey,
        machineId: machineB,
      });
      assert.strictEqual(res.ok, true);
      assert.strictEqual(res.status, "active");
    });

    it("2.5 Activation: third machine should hit DEVICE_LIMIT_REACHED", async () => {
      if (!testLifetimeKey) return;
      const res = await activateLicense({
        licenseKey: testLifetimeKey,
        machineId: machineC,
      });
      assert.strictEqual(res.ok, false);
      assert.strictEqual(res.errorCode, "DEVICE_LIMIT_REACHED");
    });

    it("2.6 Activation: invalid key should fail", async () => {
      if (!testLifetimeKey) return;
      const res = await activateLicense({
        licenseKey: "VB-9999-9999-9999-9999-9999",
        machineId: machineA,
      });
      assert.strictEqual(res.ok, false);
      assert.strictEqual(res.errorCode, "LICENSE_INVALID");
    });

    it("2.7 Validation / Refresh: valid token on machine A", async () => {
      if (!testTokenMachineA) return;
      const res = await validateLicense({
        activationToken: testTokenMachineA,
        machineId: machineA,
      });
      assert.strictEqual(res.ok, true);
      assert.strictEqual(res.status, "active");
      assert.ok(res.activationToken);
    });

    it("2.8 Validation: machine mismatch should be rejected", async () => {
      if (!testTokenMachineA) return;
      const res = await validateLicense({
        activationToken: testTokenMachineA,
        machineId: machineB,
      });
      assert.strictEqual(res.ok, false);
      assert.strictEqual(res.errorCode, "MACHINE_MISMATCH");
    });

    it("2.9 Admin: block license should revoke activation", async () => {
      if (!testLifetimeKey) return;
      const blockRes = await blockLicense(testLifetimeKey, "Test block");
      assert.strictEqual(blockRes.ok, true);

      // Validate now should return LICENSE_BLOCKED
      const valRes = await validateLicense({
        activationToken: testTokenMachineA,
        machineId: machineA,
      });
      assert.strictEqual(valRes.ok, false);
      assert.strictEqual(valRes.errorCode, "LICENSE_BLOCKED");

      // Unblock
      await unblockLicense(testLifetimeKey);
    });

    it("2.10 Deactivation: revoke machine A and allow machine C", async () => {
      if (!testTokenMachineA) return;
      const deactRes = await deactivateLicense({
        activationToken: testTokenMachineA,
        machineId: machineA,
      });
      assert.strictEqual(deactRes.ok, true);

      // Now machine C should be able to activate
      const actC = await activateLicense({
        licenseKey: testLifetimeKey,
        machineId: machineC,
      });
      assert.strictEqual(actC.ok, true);
    });
  });

  describe("3. Security Rules Assertions", () => {
    it("3.1 should confirm direct client read/write is denied in firestore.rules", () => {
      const fs = require("fs");
      const path = require("path");
      const rulesPath = path.resolve(__dirname, "../../firestore.rules");
      const rulesContent = fs.readFileSync(rulesPath, "utf8");

      assert.ok(rulesContent.includes("allow read, write: if false;"));
    });
  });
});
