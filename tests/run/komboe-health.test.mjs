import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { strength, report } from "../../scripts/komboe-health.mjs";

const login = (id, password, extra = {}) => ({ id, name: id, type: 1, login: { password, ...extra } });
const items = [
  login("a", "Same-Pass-2026!x"), login("b", "Same-Pass-2026!x", { totp: "otpauth://x" }),
  login("c", "abc"), login("d", "V3ry-Str0ng-Unique!", { uris: [{ uri: "http://old" }], totp: "t" }),
  { id: "n", type: 2, notes: "secure note" }
];

test("strength ranks weak and strong passwords", () => {
  assert.ok(strength("abc") < 5); assert.equal(strength("password123!"), 0);
  assert.ok(strength("V3ry-Str0ng-Unique!") >= 7);
});

test("report finds reuse, weak, missing 2FA and http URIs, logins only", () => {
  const r = report(items);
  assert.equal(r.total, 4);
  assert.deepEqual(r.reused.map(g => g.map(x => x.id)), [["a", "b"]]);
  assert.deepEqual(r.weak.map(x => x.id), ["c"]);
  assert.deepEqual(r.missing2fa.map(x => x.id), ["a", "c"]);
  assert.deepEqual(r.insecureUri.map(x => x.id), ["d"]);
});

test("CLI output never contains a password", () => {
  const p = spawnSync(process.execPath, [new URL("../../scripts/komboe-health.mjs", import.meta.url).pathname], { input: JSON.stringify(items), encoding: "utf8" });
  assert.equal(p.status, 0);
  assert.doesNotMatch(p.stdout, /Same-Pass|abc"|Str0ng/);
  assert.equal(JSON.parse(p.stdout).reused.length, 1);
});
