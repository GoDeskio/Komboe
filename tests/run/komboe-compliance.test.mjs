import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { complianceReport, toCsv } from "../../scripts/komboe-compliance.mjs";

const input = {
  now: "2026-10-31T00:00:00Z", maxPasswordAgeDays: 90,
  collections: [{ id: "c1", name: "Finance" }, { id: "c2", name: "Ops, EU" }],
  items: [
    { id: "a", name: "Bank", type: 1, collectionIds: ["c1"], login: { password: "Pw-A", passwordRevisionDate: "2026-01-01T00:00:00Z" } },
    { id: "b", name: "AWS", type: 1, collectionIds: ["c1", "c2"], attachments: [{}], login: { password: "Pw-B", totp: "SEED", passwordRevisionDate: "2026-10-01T00:00:00Z" } },
    { id: "c", name: "Note", type: 2, notes: "top secret note" },
    { id: "d", name: "Old", type: 1, deletedDate: "2026-05-01", login: { password: "x" } },
  ],
};

test("counts, unassigned, stale passwords and trash", () => {
  const r = complianceReport(input);
  assert.equal(r.totalItems, 3); assert.equal(r.trashed, 1);
  assert.deepEqual(r.byType, { login: 2, note: 1 });
  assert.deepEqual(r.byCollection.map(c => [c.name, c.count]), [["Finance", 2], ["Ops, EU", 1]]);
  assert.deepEqual(r.unassigned.map(x => x.id), ["c"]);
  assert.deepEqual(r.stalePasswords, [{ id: "a", name: "Bank", ageDays: 303 }]);
  assert.equal(r.loginsWithout2fa, 1); assert.equal(r.withAttachments, 1);
});

test("CSV escapes commas", () => {
  assert.match(toCsv(complianceReport(input)), /collection,c2,"Ops, EU",1/);
});

test("CLI output never contains secrets", () => {
  for (const args of [[], ["--csv"]]) {
    const p = spawnSync(process.execPath, [new URL("../../scripts/komboe-compliance.mjs", import.meta.url).pathname, ...args], { input: JSON.stringify(input), encoding: "utf8" });
    assert.equal(p.status, 0);
    assert.doesNotMatch(p.stdout, /Pw-A|Pw-B|SEED|top secret/);
  }
});
