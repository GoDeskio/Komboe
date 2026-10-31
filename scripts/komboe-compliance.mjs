#!/usr/bin/env node
// komboe-compliance: an organization compliance report, computed client-side by the admin.
// Input (one JSON object on stdin): { items: <komboe list items --organizationid X>,
//   collections: <komboe list org-collections --organizationid X>, maxPasswordAgeDays?: 90, now?: ISO }.
// Output never includes passwords, TOTP seeds, notes or field values: only ids, names and counts.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const DAY = 86400000;
const TYPES = { 1: "login", 2: "note", 3: "card", 4: "identity", 5: "ssh-key" };

export function complianceReport({ items = [], collections = [], maxPasswordAgeDays = 90, now } = {}) {
  const t = now ? Date.parse(now) : Date.now();
  const names = new Map(collections.map(c => [c.id, c.name]));
  const byCollection = new Map(collections.map(c => [c.id, 0]));
  const r = { generatedAt: new Date(t).toISOString(), maxPasswordAgeDays, totalItems: 0, byType: {}, byCollection: [],
    unassigned: [], stalePasswords: [], loginsWithout2fa: 0, withAttachments: 0, trashed: 0 };
  for (const it of items) {
    if (!it) continue;
    if (it.deletedDate) { r.trashed++; continue; }
    r.totalItems++;
    const type = TYPES[it.type] || `type-${it.type}`;
    r.byType[type] = (r.byType[type] || 0) + 1;
    const label = { id: it.id, name: it.name };
    const cols = it.collectionIds || [];
    if (!cols.length) r.unassigned.push(label);
    for (const c of cols) byCollection.set(c, (byCollection.get(c) || 0) + 1);
    if ((it.attachments || []).length) r.withAttachments++;
    if (it.type === 1 && it.login) {
      if (!it.login.totp) r.loginsWithout2fa++;
      const changed = Date.parse(it.login.passwordRevisionDate || it.revisionDate || it.creationDate || "");
      if (it.login.password && Number.isFinite(changed)) {
        const ageDays = Math.floor((t - changed) / DAY);
        if (ageDays > maxPasswordAgeDays) r.stalePasswords.push({ ...label, ageDays });
      }
    }
  }
  r.byCollection = [...byCollection].map(([id, count]) => ({ id, name: names.get(id) || "(unknown collection)", count }))
    .sort((a, b) => b.count - a.count || a.name.localeCompare(b.name));
  r.stalePasswords.sort((a, b) => b.ageDays - a.ageDays);
  return r;
}

export function toCsv(r) {
  const esc = v => /[",\n]/.test(String(v)) ? `"${String(v).replace(/"/g, '""')}"` : String(v);
  const rows = [["section", "id", "name", "value"]];
  for (const [k, v] of Object.entries(r.byType)) rows.push(["type", "", k, v]);
  for (const c of r.byCollection) rows.push(["collection", c.id, c.name, c.count]);
  for (const u of r.unassigned) rows.push(["unassigned", u.id, u.name, ""]);
  for (const s of r.stalePasswords) rows.push(["stale-password-days", s.id, s.name, s.ageDays]);
  return rows.map(row => row.map(esc).join(",")).join("\n") + "\n";
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  const r = complianceReport(JSON.parse(readFileSync(0, "utf8")));
  process.stdout.write(process.argv.includes("--csv") ? toCsv(r) : JSON.stringify(r, null, 2) + "\n");
}
