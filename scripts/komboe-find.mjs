#!/usr/bin/env node
// komboe-find: spotlight-style quick search over the decrypted JSON from `komboe list items`.
// Matches item name, username and URI hosts, ranked by match quality. Output contains only
// id, name, username and host: never passwords, TOTP seeds, notes or custom field values.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

function host(uri) {
  try { return new URL(/^[a-z]+:\/\//i.test(uri) ? uri : "https://" + uri).hostname.toLowerCase(); } catch { return ""; }
}

/** Score how well query q matches text t (higher is better, 0 means no match). */
export function score(q, t) {
  if (!q || !t) return 0;
  q = q.toLowerCase(); t = t.toLowerCase();
  if (t === q) return 100;
  if (t.startsWith(q)) return 80;
  if (t.split(/[\s._@-]+/).some(w => w.startsWith(q))) return 60;
  if (t.includes(q)) return 40;
  let i = 0, gaps = 0, last = -1;
  for (let j = 0; j < t.length && i < q.length; j++) if (t[j] === q[i]) { if (last >= 0) gaps += j - last - 1; last = j; i++; }
  return i === q.length ? Math.max(1, 20 - gaps) : 0;
}

export function find(items, query, { limit = 10 } = {}) {
  const terms = String(query).trim().split(/\s+/).filter(Boolean);
  if (!terms.length) return [];
  const out = [];
  for (const it of items || []) {
    if (!it || it.deletedDate) continue;
    const user = it.login?.username || "";
    const hosts = (it.login?.uris || []).map(u => host(u?.uri || "")).filter(Boolean);
    const fields = [[it.name || "", 1.0], [user, 0.8], ...hosts.map(h => [h, 0.9])];
    let total = 0, ok = true;
    for (const term of terms) {
      const best = Math.max(0, ...fields.map(([t, w]) => score(term, t) * w));
      if (!best) { ok = false; break; }
      total += best;
    }
    if (ok) out.push({ id: it.id, name: it.name, username: user || undefined, host: hosts[0], favorite: !!it.favorite, score: Math.round(total + (it.favorite ? 5 : 0)) });
  }
  return out.sort((a, b) => b.score - a.score || String(a.name).localeCompare(String(b.name))).slice(0, limit);
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  const q = process.argv.slice(2).join(" ");
  if (!q) { console.error("usage: komboe list items | komboe-find <query>"); process.exit(2); }
  for (const r of find(JSON.parse(readFileSync(0, "utf8")), q)) console.log([r.id, r.name, r.username || "", r.host || ""].join("\t"));
}
