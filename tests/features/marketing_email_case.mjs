/**
 * The marketing sign-in tries the typed email case, then the lowercased email.
 * A mixed-case vault salt and an existing lowercased salt both unlock.
 */
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import fs from "node:fs";
import http from "node:http";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { emailSaltCandidates, passwordHash } from "../../apps/web-marketing/assets/auth.js";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const BIN = process.env.KOMBOE_BIN || path.join(ROOT, "server/upstream/target/debug/vaultwarden");
const API = "http://127.0.0.1:18087";

function b64(raw) {
  return Buffer.from(raw).toString("base64");
}

function api(pathname, payload, token) {
  const body = payload == null ? null : JSON.stringify(payload);
  return new Promise((resolve, reject) => {
    const req = http.request(API + pathname, {
      method: payload == null ? "GET" : "POST",
      headers: {
        Accept: "application/json",
        ...(body ? { "Content-Type": "application/json", "Content-Length": Buffer.byteLength(body) } : {}),
        ...(token ? { Authorization: "Bearer " + token } : {}),
      },
    }, (res) => {
      const chunks = [];
      res.on("data", (chunk) => chunks.push(chunk));
      res.on("end", () => {
        const text = Buffer.concat(chunks).toString();
        let parsed = text;
        try { parsed = JSON.parse(text); } catch { /* keep text */ }
        resolve({ status: res.statusCode, body: parsed });
      });
    });
    req.on("error", reject);
    if (body) req.write(body);
    req.end();
  });
}

async function loginWithCandidates(typed, password, pre) {
  const salts = emailSaltCandidates(typed);
  const attempts = [];
  for (const salt of salts) {
    const hash = await passwordHash(salt, password, pre);
    const form = new URLSearchParams({
      grant_type: "password",
      username: salt,
      password: hash,
      scope: "api offline_access",
      client_id: "web",
      deviceType: "9",
      deviceIdentifier: "marketing-case",
      deviceName: "marketing-case",
    });
    const response = await new Promise((resolve, reject) => {
      const req = http.request(API + "/identity/connect/token", {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
          Accept: "application/json",
          "Content-Length": Buffer.byteLength(form.toString()),
        },
      }, (res) => {
        const chunks = [];
        res.on("data", (chunk) => chunks.push(chunk));
        res.on("end", () => {
          const text = Buffer.concat(chunks).toString();
          let parsed = text;
          try { parsed = JSON.parse(text); } catch { /* keep */ }
          resolve({ status: res.statusCode, body: parsed });
        });
      });
      req.on("error", reject);
      req.write(form.toString());
      req.end();
    });
    attempts.push(salt);
    const message = response.body && (response.body.message || response.body.error_description || response.body.Message) || "";
    const rejected = response.status === 400 && /username or password is incorrect/i.test(message);
    if (!rejected || salt === salts[salts.length - 1]) return { response, attempts };
  }
  throw new Error("no salt candidate");
}

async function register(email, password) {
  const sent = await api("/identity/accounts/register/send-verification-email", { email, name: "Case" });
  if (sent.status !== 200 || typeof sent.body !== "string") {
    throw new Error("verification " + sent.status + " " + JSON.stringify(sent.body).slice(0, 200));
  }
  const hash = await passwordHash(email, password, { kdf: 0, kdfIterations: 100000 });
  const userKey = b64(Buffer.alloc(64, 3));
  const done = await api("/identity/accounts/register/finish", {
    email,
    emailVerificationToken: sent.body,
    masterPasswordHash: hash,
    masterPasswordHint: null,
    userSymmetricKey: "2." + b64(Buffer.alloc(16, 1)) + "|" + userKey + "|" + b64(Buffer.alloc(32, 2)),
    kdf: 0,
    kdfIterations: 100000,
    userAsymmetricKeys: { publicKey: b64(Buffer.alloc(32, 4)), encryptedPrivateKey: "x" },
  });
  if (done.status !== 200) throw new Error("register " + done.status + " " + JSON.stringify(done.body).slice(0, 300));
}

async function main() {
  assert.deepEqual(emailSaltCandidates("Ada@Example.com"), ["Ada@Example.com", "ada@example.com"]);
  assert.deepEqual(emailSaltCandidates("ada@example.com"), ["ada@example.com"]);
  assert.deepEqual(emailSaltCandidates("  Ada@Example.com "), ["Ada@Example.com", "ada@example.com"]);

  const data = fs.mkdtempSync(path.join(os.tmpdir(), "komboe-case-"));
  const env = {
    ...process.env,
    DATA_FOLDER: data,
      ROCKET_ADDRESS: "127.0.0.1",
      ROCKET_PORT: "18087",
      DOMAIN: API,
      SIGNUPS_ALLOWED: "true",
      SIGNUPS_VERIFY: "false",
      WEB_VAULT_ENABLED: "false",
      SMTP_FROM: "",
      LOGIN_RATELIMIT_MAX_BURST: "100",
    LOGIN_RATELIMIT_SECONDS: "1",
  };
  delete env.SMTP_HOST;
  delete env.SMTP_PORT;
  delete env.SMTP_SECURITY;
  delete env.SMTP_FROM_NAME;
  delete env.SIGNUPS_DOMAINS_WHITELIST;
  const log = fs.openSync(path.join(data, "server.log"), "a");
  const proc = spawn(BIN, [], { env, stdio: ["ignore", log, log] });
  try {
    let alive = false;
    for (let i = 0; i < 80; i += 1) {
      try {
        const ping = await api("/alive", null);
        if (ping.status === 200) {
          alive = true;
          break;
        }
      } catch {
        await new Promise((r) => setTimeout(r, 250));
      }
    }
    if (!alive) {
      throw new Error(fs.readFileSync(path.join(data, "server.log"), "utf8").slice(-1500));
    }
    const stamp = Date.now().toString(36);
    const mixed = `Case-${stamp}@Komboe.test`;
    const lower = `plain-${stamp}b@komboe.test`;
    const password = "Marketing-Case-Password-1";
    await register(mixed, password);
    await register(lower, password);
    const pre = { kdf: 0, kdfIterations: 100000 };

    const exact = await loginWithCandidates(mixed, password, pre);
    if (!exact.response.body.access_token) {
      throw new Error("mixed-case salt did not sign in: " + JSON.stringify(exact.response.body).slice(0, 200));
    }
    assert.deepEqual(exact.attempts, [mixed]);

    const typedMixed = "Plain-" + stamp + "b@Komboe.test";
    const fallback = await loginWithCandidates(typedMixed, password, pre);
    if (!fallback.response.body.access_token) {
      throw new Error("lowercased account did not sign in: " + JSON.stringify(fallback.response.body).slice(0, 200));
    }
    assert.deepEqual(fallback.attempts, [typedMixed, typedMixed.toLowerCase()]);
    console.log("MARKETING EMAIL CASE PASS");
  } finally {
    proc.kill("SIGTERM");
    fs.closeSync(log);
    fs.rmSync(data, { recursive: true, force: true });
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
