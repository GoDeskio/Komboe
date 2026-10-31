#!/usr/bin/env node
// komboe-run: run a command with secret references resolved into its environment.
//   KEY=komboe://<item name or id>/<field>   field: username | password | notes | uri | <custom field name>
// Usage: komboe-run [--env-file .env] -- <command> [args...]
// References are resolved by the Komboe CLI (decryption stays client-side, BW_SESSION
// must be an unlocked session). Resolved values go only to the child's environment.
import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

export const REF = /^komboe:\/\/([^/]+)\/(.+)$/;

export function parseRef(value) {
  const m = REF.exec(String(value ?? ""));
  return m ? { item: decodeURIComponent(m[1]), field: decodeURIComponent(m[2]) } : null;
}

export function parseEnvFile(text) {
  const out = {};
  for (const line of text.split(/\r?\n/)) {
    const m = /^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$/.exec(line);
    if (!m || line.trim().startsWith("#")) continue;
    out[m[1]] = m[2].replace(/^(['"])(.*)\1$/, "$2");
  }
  return out;
}

export function pickField(item, field) {
  const login = item.login || {};
  if (field === "username") return login.username;
  if (field === "password") return login.password;
  if (field === "notes") return item.notes;
  if (field === "uri") return login.uris?.[0]?.uri;
  return (item.fields || []).find(f => f.name === field)?.value;
}

// getItem(name) -> parsed item JSON. Each item is fetched once.
export function resolveEnv(env, getItem) {
  const cache = new Map(), out = { ...env }, errors = [];
  for (const [key, value] of Object.entries(env)) {
    const ref = parseRef(value);
    if (!ref) continue;
    try {
      if (!cache.has(ref.item)) cache.set(ref.item, getItem(ref.item));
      const v = pickField(cache.get(ref.item), ref.field);
      if (v == null) errors.push(`${key}: field "${ref.field}" not found`);
      else out[key] = String(v);
    } catch (e) {
      errors.push(`${key}: ${e.message}`);
    }
  }
  return { env: out, errors };
}

function cliGetItem(name) {
  const bw = process.env.KOMBOE_CLI || join(dirname(fileURLToPath(import.meta.url)), "../clients/upstream/apps/cli/build/bw.js");
  const r = spawnSync(process.execPath, [bw, "get", "item", name, "--raw"], { encoding: "utf8", env: process.env });
  if (r.status !== 0) throw new Error(`item "${name}" could not be read (is the vault unlocked?)`);
  return JSON.parse(r.stdout);
}

function main(argv) {
  const sep = argv.indexOf("--");
  if (sep < 0 || sep === argv.length - 1) {
    console.error("Usage: komboe-run [--env-file FILE] -- <command> [args...]");
    return 2;
  }
  let env = { ...process.env };
  const i = argv.indexOf("--env-file");
  if (i >= 0 && i < sep) env = { ...env, ...parseEnvFile(readFileSync(argv[i + 1], "utf8")) };
  const { env: resolved, errors } = resolveEnv(env, cliGetItem);
  if (errors.length) {
    errors.forEach(e => console.error("komboe-run: " + e));
    return 1;
  }
  const [cmd, ...args] = argv.slice(sep + 1);
  const r = spawnSync(cmd, args, { stdio: "inherit", env: resolved });
  return r.status ?? 1;
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) process.exit(main(process.argv.slice(2)));
