import { spawn } from "node:child_process";
import crypto from "node:crypto";
import fs from "node:fs";
import http from "node:http";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import playwright from "../../apps/web-marketing/node_modules/playwright/index.js";

const { chromium } = playwright;

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const shots = "/opt/cursor/artifacts";
const apiPort = 18083;
const webPort = 4175;
const bin = process.env.KOMBOE_BIN || path.join(root, "server/upstream/target/debug/vaultwarden");

function b64(buf) {
  return Buffer.from(buf).toString("base64");
}

function pbkdf(password, salt, iterations, length) {
  return crypto.pbkdf2Sync(password, salt, iterations, length, "sha256");
}

async function waitFor(url) {
  for (let i = 0; i < 80; i += 1) {
    try {
      const response = await fetch(url);
      if (response.ok || response.status === 404) return;
    } catch {
      await new Promise((resolve) => setTimeout(resolve, 250));
    }
  }
  throw new Error(`not up: ${url}`);
}

const data = fs.mkdtempSync(path.join(os.tmpdir(), "komboe-ui-"));
const server = spawn(bin, [], {
  env: {
    ...process.env,
    DATA_FOLDER: data,
    ROCKET_ADDRESS: "127.0.0.1",
    ROCKET_PORT: String(apiPort),
    DOMAIN: `http://127.0.0.1:${webPort}`,
    SIGNUPS_ALLOWED: "true",
    SIGNUPS_VERIFY: "false",
    WEB_VAULT_ENABLED: "false",
    SMTP_FROM: "",
  },
  stdio: "ignore",
});
const web = spawn("python3", ["serve.py", "--host", "127.0.0.1", "--port", String(webPort), "--api", `http://127.0.0.1:${apiPort}`], {
  cwd: path.join(root, "apps/web-marketing"),
  stdio: "ignore",
});
const files = http.createServer((req, res) => {
  const rel = decodeURIComponent((req.url || "/").split("?")[0]).replace(/^\/+/, "");
  const file = path.join(root, rel);
  if (!file.startsWith(root) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) {
    res.writeHead(404);
    res.end("missing");
    return;
  }
  const type = file.endsWith(".mjs") || file.endsWith(".js") ? "text/javascript" : "text/html";
  res.writeHead(200, { "Content-Type": type });
  fs.createReadStream(file).pipe(res);
});

try {
  await new Promise((resolve) => files.listen(8765, "127.0.0.1", resolve));
  await waitFor(`http://127.0.0.1:${apiPort}/alive`);
  await waitFor(`http://127.0.0.1:${webPort}/`);

  const browser = await chromium.launch({
    executablePath:
      process.env.CHROME_PATH ||
      (fs.existsSync("/usr/local/bin/google-chrome")
        ? "/usr/local/bin/google-chrome"
        : playwright.chromium.executablePath()),
    args: ["--no-sandbox", "--disable-dev-shm-usage"],
  });
  const page = await browser.newPage({ viewport: { width: 1400, height: 900 } });

  const email = `ui-${crypto.randomBytes(3).toString("hex")}@komboe.test`;
  const password = "Ui-Proof-Password-1";
  const iterations = 100000;
  const verify = await fetch(`http://127.0.0.1:${apiPort}/identity/accounts/register/send-verification-email`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({ email, name: "UI" }),
  });
  const token = await verify.json();
  const master = pbkdf(password, email, iterations, 32);
  const hash = b64(pbkdf(master, password, 1, 32));
  const finish = await fetch(`http://127.0.0.1:${apiPort}/identity/accounts/register/finish`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({
      email,
      emailVerificationToken: token,
      masterPasswordHash: hash,
      masterPasswordHint: null,
      userSymmetricKey: `2.${b64(crypto.randomBytes(16))}|${b64(crypto.randomBytes(64))}|${b64(crypto.randomBytes(32))}`,
      kdf: 0,
      kdfIterations: iterations,
      userAsymmetricKeys: { publicKey: b64(crypto.randomBytes(32)), encryptedPrivateKey: "x" },
    }),
  });
  if (!finish.ok) throw new Error(`register ${finish.status} ${await finish.text()}`);

  await page.goto(`http://127.0.0.1:${webPort}/`);
  await page.fill("#email", email);
  await page.fill("#master-password", password);
  await page.click("#login-submit");
  await page.waitForURL(/\/vault\/?$/);
  await page.locator("#dash-email").waitFor();
  const dashText = await page.locator("#dash-email").innerText();
  if (dashText !== email) throw new Error(`dashboard email ${dashText}`);
  await page.screenshot({ path: path.join(shots, "signed-in-vault.png"), fullPage: true });

  await page.goto(`http://127.0.0.1:${webPort}/downloads.html`);
  await page.locator("[data-testid='downloads-manifest-empty']").waitFor();
  await page.screenshot({ path: path.join(shots, "dashboard-downloads.png"), fullPage: false });

  const unlock = await browser.newPage({ viewport: { width: 900, height: 800 } });
  const errors = [];
  unlock.on("pageerror", (error) => errors.push(String(error)));
  unlock.on("requestfailed", (request) => {
    if (request.url().includes("favicon")) return;
    errors.push(`${request.url()} ${request.failure()?.errorText}`);
  });
  await unlock.goto("http://127.0.0.1:8765/tests/features/device_unlock_fixture.html");
  await unlock.waitForTimeout(1000);
  if (!await unlock.evaluate(() => Boolean(window.komboeDevice))) {
    throw new Error(errors.join("\n") || "module did not load");
  }
  if (errors.length) throw new Error(errors.join("\n"));
  await unlock.evaluate(() => document.getElementById("enroll").click());
  await unlock.waitForFunction(() => document.getElementById("out").textContent.includes("PIN enrolled"));
  await unlock.screenshot({ path: path.join(shots, "pin-enrolled.png") });
  await unlock.evaluate(() => document.getElementById("unlock").click());
  await unlock.waitForFunction(() => document.getElementById("out").textContent.includes("Unlocked"));
  await unlock.screenshot({ path: path.join(shots, "pin-unlocked.png") });
  await unlock.evaluate(() => document.getElementById("wrong").click());
  await unlock.waitForFunction(() => document.getElementById("err").textContent.includes("did not match"));
  await unlock.screenshot({ path: path.join(shots, "pin-failed.png") });
  await unlock.screenshot({ path: path.join(shots, "pin-failed.png") });
  await browser.close();
  console.log("UI PROOF PASS");
} finally {
  server.kill();
  web.kill();
  files.close();
  fs.rmSync(data, { recursive: true, force: true });
}
