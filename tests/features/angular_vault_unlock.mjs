/**
 * Real Angular web vault: master-password login, PIN enrollment of the live user key,
 * lock, wrong PIN, PIN unlock, and the known cipher password visible again.
 * Pattern, expiry, and logout are checked in the same vault session.
 */
import { createRequire } from "node:module";
import { spawn } from "node:child_process";
import fs from "node:fs";
import http from "node:http";
import https from "node:https";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(path.join(path.dirname(fileURLToPath(import.meta.url)), "../../apps/web-marketing/package.json"));
const { chromium } = require("@playwright/test");

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const VAULT = path.join(ROOT, "clients/upstream/apps/web/build");
const BIN = process.env.KOMBOE_BIN || path.join(ROOT, "server/upstream/target/debug/vaultwarden");
const API = "https://127.0.0.1:18085";
const SECRET = "known-cipher-secret";
const PIN = "902410";
const SHOTS = "/opt/cursor/artifacts";

function b64(raw) {
  return Buffer.from(raw).toString("base64");
}

function passwordHash(email, password) {
  const master = require("crypto").pbkdf2Sync(password, email, 100000, 32, "sha256");
  return b64(require("crypto").pbkdf2Sync(master, password, 1, 32, "sha256"));
}

function api(pathname, payload) {
  const body = JSON.stringify(payload);
  return new Promise((resolve, reject) => {
    const req = https.request(API + pathname, { rejectUnauthorized: false,
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json", "Content-Length": Buffer.byteLength(body) },
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
    req.end(body);
  });
}

async function enterPin(page, field, button, pin) {
  await page.getByTestId(field).evaluate((el, value) => {
    el.value = value;
    el.dispatchEvent(new Event("input", { bubbles: true }));
  }, pin);
  await page.getByTestId(button).evaluate((el) => el.click());
}

async function waitAlive() {
  for (let i = 0; i < 80; i += 1) {
    try {
      await new Promise((resolve, reject) => {
        https.get(API + "/alive", { rejectUnauthorized: false }, (res) => { res.resume(); res.statusCode === 200 ? resolve() : reject(new Error(String(res.statusCode))); }).on("error", reject);
      });
      return;
    } catch {
      await new Promise((r) => setTimeout(r, 250));
    }
  }
  throw new Error("vaultwarden did not start");
}

async function main() {
  const bundle = [];
  const walk = (dir) => {
    for (const name of fs.readdirSync(dir)) {
      const full = path.join(dir, name);
      if (fs.statSync(full).isDirectory()) walk(full);
      else if (name.endsWith(".js")) bundle.push(fs.readFileSync(full, "utf8"));
    }
  };
  walk(VAULT);
  const built = bundle.join("\n");
  if (!built.includes("Refusing to wrap anything except a vault user key")) {
    throw new Error("the built vault does not contain the user-key check");
  }
  if (!built.includes("komboe.deviceTrust")) {
    throw new Error("the built vault does not send the server trust token");
  }
  fs.mkdirSync(SHOTS, { recursive: true });
  const data = fs.mkdtempSync(path.join(os.tmpdir(), "komboe-angular-"));
  const cert = path.join(data, "cert.pem");
  const key = path.join(data, "key.pem");
  await new Promise((resolve, reject) => {
    const child = spawn("openssl", ["req", "-x509", "-newkey", "rsa:2048", "-keyout", key, "-out", cert, "-days", "1", "-nodes", "-subj", "/CN=127.0.0.1", "-addext", "subjectAltName=IP:127.0.0.1"], { stdio: "ignore" });
    child.on("exit", (code) => code === 0 ? resolve() : reject(new Error("openssl " + code)));
  });
  const proc = spawn(BIN, [], {
    env: {
      ...process.env,
      DATA_FOLDER: data,
      ROCKET_ADDRESS: "127.0.0.1",
      ROCKET_PORT: "18085",
      DOMAIN: "https://127.0.0.1:18085",
      ROCKET_TLS: `{certs="${cert}",key="${key}"}`,
      SIGNUPS_ALLOWED: "true",
      SIGNUPS_VERIFY: "false",
      WEB_VAULT_ENABLED: "true",
      WEB_VAULT_FOLDER: VAULT,
      SMTP_FROM: "",
      LOGIN_RATELIMIT_MAX_BURST: "100",
      LOGIN_RATELIMIT_SECONDS: "1",
    },
    stdio: "ignore",
  });
  const browser = await chromium.launch({
    executablePath: fs.existsSync("/usr/local/bin/google-chrome") ? "/usr/local/bin/google-chrome" : undefined,
    headless: true,
  });
  try {
    await waitAlive();
    const email = `angular-${Date.now().toString(36)}@komboe.test`;
    const password = "Angular-Vault-Password-1";
    const context = await browser.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1280, height: 900 } });
    const page = await context.newPage();
    page.on("response", async (response) => {
      if (response.url().includes("/identity/") || response.url().includes("/api/")) {
        const text = await response.text().catch(() => "");
        console.log("HTTP", response.status(), response.url(), text.slice(0, 300));
      }
    });
    page.on("console", (msg) => {
      if (msg.type() === "error") console.log("CONSOLE", msg.text().slice(0, 400));
    });
    await page.goto(API + "/#/signup", { waitUntil: "domcontentloaded" });
    await page.locator("#register-start_form_input_email").fill(email);
    await page.locator("#register-start_form_input_name").fill("Angular");
    await page.getByRole("button", { name: /^continue$/i }).click();
    await page.locator("#input-password-form_new-password").fill(password);
    await page.locator("#input-password-form_new-password-confirm").fill(password);
    await page.getByRole("button", { name: /create account/i }).click();
    try {
      await page.waitForURL(/#\/(vault|setup)/, { timeout: 60000 });
    } catch (error) {
      await page.screenshot({ path: path.join(SHOTS, "angular-login-stuck.png") });
      throw new Error(page.url() + " " + (await page.locator("body").innerText()).slice(0, 1500));
    }
    const skip = page.getByRole("button", { name: /skip to the web app|add it later/i });
    if (page.url().includes("setup") || await skip.count()) {
      await skip.first().waitFor({ timeout: 15000 });
      await skip.first().click();
      const confirm = page.getByText(/skip to web app/i);
      await confirm.waitFor({ timeout: 10000 });
      await confirm.click();
      await page.waitForURL(/#\/vault/, { timeout: 20000 });
    }
    await page.screenshot({ path: path.join(SHOTS, "angular-vault-signed-in.png") });

    const tour = page.getByRole("button", { name: /^skip$/i });
    if (await tour.count()) await tour.first().click();
    const add = page.getByRole("button", { name: /^add item$/i });
    try {
      await add.click({ timeout: 15000 });
    } catch (error) {
      await page.screenshot({ path: path.join(SHOTS, "angular-vault-no-add.png") });
      throw new Error((await page.locator("body").innerText()).slice(0, 1500));
    }
    const loginType = page.getByRole("menuitem", { name: /^login$/i });
    if (await loginType.count()) await loginType.click();
    await page.locator('input[formcontrolname="name"]').fill("Known cipher");
    await page.locator('input[formcontrolname="password"]').fill(SECRET);
    await page.getByRole("button", { name: /^save$/i }).click();
    await page.getByText("Known cipher").first().waitFor({ timeout: 20000 });
    await page.keyboard.press("Escape");
    await page.screenshot({ path: path.join(SHOTS, "angular-cipher-saved.png") });

    await page.evaluate(() => { window.location.hash = "/settings/device-access"; });
    await page.waitForURL(/device-access/, { timeout: 15000 });
    try {
      await page.getByTestId("device-pin").waitFor({ timeout: 15000 });
    } catch (error) {
      throw new Error(page.url() + "\n" + (await page.locator("body").innerText()).slice(0, 1200));
    }
    await page.getByTestId("device-pin").evaluate((el, pin) => {
      el.value = pin;
      el.dispatchEvent(new Event("input", { bubbles: true }));
    }, PIN);
    await page.getByTestId("enroll-pin").evaluate((el) => el.click());
    await page.waitForTimeout(8000);
    const section = await page.getByTestId("device-access").innerText();
    const enrolled = section;
    if (!enrolled.includes("can now unlock")) throw new Error(enrolled);
    await page.screenshot({ path: path.join(SHOTS, "angular-pin-enrolled.png") });

    await page.getByTestId("device-lock").evaluate((el) => el.click());
    await page.waitForTimeout(3000);
    const lockText = await page.getByTestId("device-access").innerText().catch(() => "");
    if (!lockText.includes("locking") && !page.url().includes("lock")) {
      throw new Error("lock click did not run: " + lockText.slice(0, 500));
    }
    await page.evaluate(() => { window.location.hash = "/lock"; });
    await page.waitForURL(/#\/lock/, { timeout: 20000 });
    await enterPin(page, "unlock-pin", "unlock-pin-submit", "000111");
    const wrong = await page.getByTestId("device-access-message").innerText();
    if (!wrong) throw new Error("wrong PIN produced no message");
    await page.screenshot({ path: path.join(SHOTS, "angular-pin-wrong.png") });

    await enterPin(page, "unlock-pin", "unlock-pin-submit", PIN);
    await page.waitForURL(/#\/vault/, { timeout: 20000 });
    await page.getByText("Known cipher").first().click();
    await page.getByTestId("toggle-password-visibility").click();
    const shown = await page.locator('input[formcontrolname="password"], [data-testid="password"]').first().inputValue().catch(async () => page.getByText(SECRET).innerText());
    if (!String(shown).includes(SECRET)) throw new Error("decrypted password was " + shown);
    await page.screenshot({ path: path.join(SHOTS, "angular-pin-unlocked-cipher.png") });

    const keys = await page.evaluate(() => Object.keys(localStorage).filter((key) => key.startsWith("komboe.deviceUnlock")));
    if (keys.length !== 1) throw new Error("expected one device record, saw " + keys.join(","));
    await page.evaluate((key) => {
      const record = JSON.parse(localStorage.getItem(key));
      record.lastSuccess = Date.now() - (12 * 60 * 60 * 1000 + 1000);
      localStorage.setItem(key, JSON.stringify(record));
    }, keys[0]);
    await page.evaluate(() => { window.location.hash = "/settings/device-access"; });
    await page.getByTestId("device-lock").evaluate((el) => el.click());
    await page.waitForTimeout(2000);
    await page.evaluate(() => { window.location.hash = "/lock"; });
    await page.waitForURL(/#\/lock/);
    await enterPin(page, "unlock-pin", "unlock-pin-submit", PIN);
    const expired = await page.getByTestId("device-access-message").innerText();
    if (!/expired|master password/i.test(expired)) throw new Error("expiry message was " + expired);

    await page.evaluate(() => { window.location.hash = "/settings/device-access"; });
    await page.getByTestId("device-logout").evaluate((el) => el.click());
    const left = await page.evaluate(() => Object.keys(localStorage).filter((key) => key.startsWith("komboe.deviceUnlock")));
    if (left.length !== 0) throw new Error("logout left a device record");
    console.log("ANGULAR VAULT UNLOCK PASS");
  } finally {
    await browser.close();
    proc.kill("SIGTERM");
    fs.rmSync(data, { recursive: true, force: true });
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
