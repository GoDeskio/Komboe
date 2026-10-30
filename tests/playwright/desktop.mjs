// Komboe desktop (Electron, Linux) smoke E2E: launch the packaged app, pick the self-hosted server, log in, see the vault.
// Usage: KOMBOE_DESKTOP=<linux-unpacked dir> node desktop.mjs   (needs a DISPLAY; uses fixtures.local.json "ext" user)
import fs from "fs"; import path from "path"; import os from "os"; import { fileURLToPath } from "url";
const here = path.dirname(fileURLToPath(import.meta.url));
const { _electron } = await import(path.join(process.env.PLAYWRIGHT_DIR || "/workspace/up/bw-oss/node_modules/playwright", "index.mjs"));
const DIR = process.env.KOMBOE_DESKTOP || "/workspace/up/bw-oss/apps/desktop/dist/linux-unpacked";
const WEB = process.env.KOMBOE_WEB || "https://localhost:8443"; const SHOTS = path.join(here, "../../docs/screenshots");
const fx = JSON.parse(fs.readFileSync(path.join(here, "fixtures.local.json")));
const rpath = path.join(here, "results.json"); const results = fs.existsSync(rpath) ? JSON.parse(fs.readFileSync(rpath)) : {};
const home = fs.mkdtempSync(path.join(os.tmpdir(), "komboe-desk-"));
let app;
async function step(name, fn) { try { await fn(); results[name] = "passed"; console.log("PASS", name); }
  catch (e) { results[name] = "failed"; console.log("FAIL", name, String(e.message || e).replace(/\s+/g, " ").slice(0, 300)); } }
await step("desktop-launch", async () => {
  app = await _electron.launch({ executablePath: path.join(DIR, "bitwarden-app"), args: ["--no-sandbox", "--ignore-certificate-errors"],
    env: { ...process.env, HOME: home, XDG_CONFIG_HOME: path.join(home, ".config"), ELECTRON_IS_DEV: "0" }, timeout: 60000 });
  const w = await app.firstWindow(); await w.waitForSelector("text=Komboe", { timeout: 60000 });
  await w.waitForTimeout(3000); await w.screenshot({ path: path.join(SHOTS, "desktop-welcome.png") });
});
if (results["desktop-launch"] === "passed") await step("desktop-login", async () => {
  const w = await app.firstWindow(); w.setDefaultTimeout(30000);
  for (let i = 0; i < 5 && !(await w.getByText("Accessing").count()); i++) {
    const li = w.locator("a, button").filter({ hasText: /^\s*Log in\s*$/ }); if (await li.count()) await li.last().click().catch(() => {}); await w.waitForTimeout(2500); }
  await w.locator("button", { hasText: "Choose your Komboe server" }).first().click(); await w.waitForTimeout(800);
  if (/bitwarden\.(com|eu)/.test(await w.evaluate(() => document.body.innerText))) throw new Error("desktop server picker offers Bitwarden cloud");
  await w.locator("button", { hasText: "self-hosted" }).first().click();
  await w.getByLabel("Server URL").fill(WEB); await w.getByRole("button", { name: "Save" }).click(); await w.waitForTimeout(1500);
  await w.fill("#email", fx.ext.email); await w.getByRole("button", { name: "Continue" }).click();
  await w.fill("#masterPassword", fx.ext.pw); await w.getByRole("button", { name: "Log in", exact: true }).click();
  await w.getByText("Autofill test").first().waitFor({ timeout: 60000 }); await w.waitForTimeout(1500);
  await w.screenshot({ path: path.join(SHOTS, "desktop-vault.png") });
});
if (app) await app.close().catch(() => {});
fs.rmSync(home, { recursive: true, force: true });
fs.writeFileSync(rpath, JSON.stringify(results, null, 1) + "\n");
