#!/usr/bin/env node
// komboe-health: client-side vault health report (reused, weak, missing 2FA, insecure URL).
// Input is the decrypted JSON from `komboe list items` (read from stdin or produced via
// the CLI with an unlocked session). Passwords never leave this process and are never printed;
// reuse is detected with salted in-memory SHA-256 digests.
import { createHash, randomBytes } from "node:crypto";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

export function strength(pw) {
  if (!pw) return 0;
  const classes = [/[a-z]/, /[A-Z]/, /[0-9]/, /[^A-Za-z0-9]/].filter(r => r.test(pw)).length;
  let score = Math.min(4, Math.floor(pw.length / 4)) + classes;
  if (/^(.)\1+$/.test(pw) || /^(password|letmein|qwerty|123456)/i.test(pw)) score = 0;
  return score; // 0..8
}

export function report(items, { weakBelow = 5 } = {}) {
  const salt = randomBytes(16), groups = new Map();
  const out = { total: 0, reused: [], weak: [], missing2fa: [], insecureUri: [] };
  for (const it of items) {
    const l = it?.login;
    if (it?.type !== 1 || !l) continue;
    out.total++;
    const label = { id: it.id, name: it.name };
    if (l.password) {
      const h = createHash("sha256").update(salt).update(l.password).digest("hex");
      groups.set(h, [...(groups.get(h) || []), label]);
      if (strength(l.password) < weakBelow) out.weak.push(label);
    }
    if (!l.totp) out.missing2fa.push(label);
    if ((l.uris || []).some(u => /^http:\/\//i.test(u?.uri || ""))) out.insecureUri.push(label);
  }
  for (const g of groups.values()) if (g.length > 1) out.reused.push(g);
  out.score = out.total ? Math.round(100 * (1 - (out.weak.length + out.reused.flat().length) / (2 * out.total))) : 100;
  return out;
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  const r = report(JSON.parse(readFileSync(0, "utf8")));
  console.log(JSON.stringify(r, null, 2));
}
