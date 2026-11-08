import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

import {
  MAX_FAILURES,
  UNLOCK_TTL_MS,
  biometricCapability,
  assertVaultUserKey,
  enrollDeviceUnlock,
  recordHoldsPlaintext,
  storageKey,
  unlockDevice,
  validatePattern,
  validatePin,
} from "../../clients/upstream/apps/web/src/app/auth/komboe-device-unlock.mjs";
import { kdfIdentity, loginIdentifierAccepted } from "../../clients/upstream/libs/common/src/auth/kdf-identity.ts";

test("email keeps its exact characters and a login name cannot derive a key", () => {
  assert.equal(kdfIdentity("Ada@Example.com", "other@example.com"), "Ada@Example.com");
  assert.equal(kdfIdentity("ada", "ada@example.com"), "ada@example.com");
  assert.throws(() => kdfIdentity("ada", null), /will not derive/);
  assert.equal(loginIdentifierAccepted("ada"), true);
  assert.equal(loginIdentifierAccepted("ab"), false);
  assert.equal(loginIdentifierAccepted("ada@example.com"), true);
});

test("pin and pattern wrap the user key and reject weak secrets", async () => {
  const userKey = crypto.getRandomValues(new Uint8Array(64));
  assert.equal(validatePin("123456"), "That PIN is too easy to guess.");
  assert.equal(validatePattern("1111"), "Each dot can be used once.");
  const record = await enrollDeviceUnlock(userKey, "902410", "pin");
  assert.equal(recordHoldsPlaintext(record, "902410", userKey), false);
  assert.equal(JSON.stringify(record).includes("master"), false);
  const opened = await unlockDevice(record, "902410");
  assert.equal(Buffer.from(opened.userKey).equals(Buffer.from(userKey)), true);

  let current = record;
  for (let i = 1; i < MAX_FAILURES; i += 1) {
    const failed = await unlockDevice(current, "000111");
    assert.equal(failed.userKey, null);
    assert.equal(failed.wiped, false);
    current = failed.record;
    assert.equal(current.failures, i);
  }
  const wiped = await unlockDevice(current, "000111");
  assert.equal(wiped.wiped, true);
  assert.equal(wiped.record, null);
});

test("pattern roundtrip and expiry require the master password again", async () => {
  const userKey = crypto.getRandomValues(new Uint8Array(64));
  const record = await enrollDeviceUnlock(userKey, "0486", "pattern");
  const opened = await unlockDevice(record, "0486");
  assert.equal(Buffer.from(opened.userKey).equals(Buffer.from(userKey)), true);
  const expired = await unlockDevice({ ...record, lastSuccess: Date.now() - UNLOCK_TTL_MS - 1 }, "0486");
  assert.equal(expired.expired, true);
  assert.equal(expired.userKey, null);
  assert.equal(storageKey("user-1"), "komboe.deviceUnlock.v1.user-1");
});

test("a 64-byte vault user key roundtrips and a token does not", async () => {
  const userKey = crypto.getRandomValues(new Uint8Array(64));
  assertVaultUserKey(userKey);
  const record = await enrollDeviceUnlock(userKey, "902410", "pin");
  const opened = await unlockDevice(record, "902410");
  assert.equal(Buffer.from(opened.userKey).equals(Buffer.from(userKey)), true);
  assert.throws(() => assertVaultUserKey(new Uint8Array(16)), /vault user key/);
  const source = fs.readFileSync(
    new URL("../../clients/upstream/apps/web/src/app/auth/komboe-device-access.component.ts", import.meta.url),
    "utf8",
  );
  assert.match(source, /userKey\.toEncoded\(\)/);
  assert.match(source, /unlockWithDecryptedUserKey/);
  assert.match(source, /assertVaultUserKey\(result\.userKey\)/);
});

test("biometrics are reported honestly and no sample is stored", () => {
  const missing = biometricCapability({});
  assert.equal(missing.supported, false);
  assert.match(missing.reason, /does not collect/);
  const present = biometricCapability({ credentials: { create() {} } });
  globalThis.PublicKeyCredential = function PublicKeyCredential() {};
  const withWebAuthn = biometricCapability({ credentials: { create() {} } });
  assert.equal(withWebAuthn.supported, true);
  assert.match(withWebAuthn.reason, /never receives a biometric sample/);
  assert.equal(present.supported, false);
  delete globalThis.PublicKeyCredential;
});
