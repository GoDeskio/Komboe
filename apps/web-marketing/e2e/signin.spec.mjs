import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { test, expect } from "@playwright/test";

const API = process.env.KOMBOE_API || "http://127.0.0.1:18080";
const shots = path.join(path.dirname(new URL(import.meta.url).pathname), "screenshots");

function b64(buf) {
  return Buffer.from(buf).toString("base64");
}

function hkdfExpand(prk, info, length) {
  let previous = Buffer.alloc(0);
  let out = Buffer.alloc(0);
  let counter = 1;
  while (out.length < length) {
    const hmac = crypto.createHmac("sha256", prk);
    hmac.update(previous);
    hmac.update(info);
    hmac.update(Buffer.from([counter]));
    previous = hmac.digest();
    out = Buffer.concat([out, previous]);
    counter += 1;
  }
  return out.subarray(0, length);
}

function enc(plain, key64) {
  const iv = crypto.randomBytes(16);
  const cipher = crypto.createCipheriv("aes-256-cbc", key64.subarray(0, 32), iv);
  const ct = Buffer.concat([cipher.update(plain), cipher.final()]);
  const mac = crypto.createHmac("sha256", key64.subarray(32)).update(iv).update(ct).digest();
  return `2.${b64(iv)}|${b64(ct)}|${b64(mac)}`;
}

function b32decode(input) {
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
  const clean = input.toUpperCase().replace(/=+$/, "");
  let bits = "";
  for (const char of clean) {
    const value = alphabet.indexOf(char);
    if (value < 0) throw new Error("bad base32");
    bits += value.toString(2).padStart(5, "0");
  }
  const out = [];
  for (let i = 0; i + 8 <= bits.length; i += 8) out.push(parseInt(bits.slice(i, i + 8), 2));
  return Buffer.from(out);
}

function totp(secret, at = Date.now()) {
  const key = b32decode(secret);
  const counter = Buffer.alloc(8);
  counter.writeBigUInt64BE(BigInt(Math.floor(at / 1000 / 30)));
  const mac = crypto.createHmac("sha1", key).update(counter).digest();
  const offset = mac[mac.length - 1] & 15;
  const code = mac.readUInt32BE(offset) & 0x7fffffff;
  return String(code % 1000000).padStart(6, "0");
}

async function api(pathname, { method = "POST", json, form, token, accept = "application/json" } = {}) {
  const headers = {
    Accept: accept,
    "Device-Type": "9",
    "Bitwarden-Client-Name": "web",
    "Bitwarden-Client-Version": "2026.10.1",
  };
  let body;
  if (form) {
    headers["Content-Type"] = "application/x-www-form-urlencoded";
    body = new URLSearchParams(form);
  } else if (json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(json);
  }
  if (token) headers.Authorization = "Bearer " + token;
  const response = await fetch(API + pathname, { method, headers, body });
  const text = await response.text();
  let parsed = text;
  try { parsed = text ? JSON.parse(text) : null; } catch { parsed = text; }
  return { status: response.status, body: parsed };
}

test("home page signs in to the real vault, including two-step login", async ({ page }) => {
  fs.mkdirSync(shots, { recursive: true });
  const email = `mkt-${crypto.randomBytes(4).toString("hex")}@komboe.test`;
  const password = "Komboe-Mkt-" + crypto.randomBytes(6).toString("hex");
  const iterations = 100000;
  const master = crypto.pbkdf2Sync(password, email, iterations, 32, "sha256");
  const hash = b64(crypto.pbkdf2Sync(master, password, 1, 32, "sha256"));
  const userKey = crypto.randomBytes(64);
  const stretched = Buffer.concat([
    hkdfExpand(master, Buffer.from("enc"), 32),
    hkdfExpand(master, Buffer.from("mac"), 32),
  ]);
  const keys = crypto.generateKeyPairSync("rsa", { modulusLength: 2048 });
  const pub = keys.publicKey.export({ type: "spki", format: "der" });
  const priv = keys.privateKey.export({ type: "pkcs8", format: "der" });
  const verify = await api("/identity/accounts/register/send-verification-email", {
    json: { email, name: "Marketing" },
  });
  if (verify.status !== 200 || typeof verify.body !== "string") {
    throw new Error("register token failed " + verify.status + " " + JSON.stringify(verify.body).slice(0, 200));
  }
  const finish = await api("/identity/accounts/register/finish", {
    json: {
      email,
      emailVerificationToken: verify.body,
      masterPasswordHash: hash,
      masterPasswordHint: null,
      userSymmetricKey: enc(userKey, stretched),
      kdf: 0,
      kdfIterations: iterations,
      userAsymmetricKeys: {
        publicKey: b64(pub),
        encryptedPrivateKey: enc(priv, userKey),
      },
    },
  });
  if (finish.status !== 200) throw new Error("register finish " + finish.status + " " + JSON.stringify(finish.body).slice(0, 300));

  const login = await api("/identity/connect/token", {
    form: {
      grant_type: "password",
      username: email,
      password: hash,
      scope: "api offline_access",
      client_id: "web",
      deviceType: "9",
      deviceIdentifier: crypto.randomUUID(),
      deviceName: "marketing-setup",
    },
  });
  if (!login.body?.access_token) throw new Error("setup login failed " + login.status);
  const secret = await api("/api/two-factor/get-authenticator", {
    json: { masterPasswordHash: hash },
    token: login.body.access_token,
  });
  const code = totp(secret.body.key);
  const enabled = await api("/api/two-factor/authenticator", {
    method: "PUT",
    json: { key: secret.body.key, token: code, masterPasswordHash: hash },
    token: login.body.access_token,
  });
  if (enabled.status !== 200) throw new Error("enable 2fa " + enabled.status + " " + JSON.stringify(enabled.body).slice(0, 200));

  await page.goto("/");
  await expect(page.locator("#signin")).toBeVisible();
  await page.screenshot({ path: path.join(shots, "home-desktop.png"), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: path.join(shots, "home-mobile.png"), fullPage: true });
  await page.setViewportSize({ width: 1280, height: 800 });

  await page.fill("#email", email);
  await page.fill("#master-password", "wrong-password-value");
  await page.locator("#login-submit").click({ force: true });
  await expect(page.locator("#login-error")).toContainText("incorrect", { timeout: 60000 });

  await page.fill("#master-password", password);
  await page.locator("#login-submit").click({ force: true });
  await expect(page.locator("#twofactor")).toBeVisible({ timeout: 60000 });
  const loginCode = totp(secret.body.key, Date.now() + 30000);
  await page.locator("#twofactor-code").fill(loginCode, { force: true });
  await page.locator("#login-submit").click({ force: true });
  await page.waitForURL(/\/vault\/?$/);
  await expect(page.getByRole("heading", { name: "Your vault" })).toBeVisible();
  await expect(page.locator("#dash-email")).toHaveText(email);
  await expect(page.locator("#dash-count")).toHaveText("0");
  await page.screenshot({ path: path.join(shots, "vault-desktop.png"), fullPage: true });
  await page.goto("/");
  await expect(page.locator("#open-dashboard")).toBeVisible();
  await expect(page.locator("#login-form")).toBeHidden();
});
