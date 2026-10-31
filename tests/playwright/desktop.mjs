// Komboe desktop (Electron, Linux) smoke E2E: launch the packaged app, pick the self-hosted server, log in, see the vault.
// Usage: KOMBOE_DESKTOP=<linux-unpacked dir> node desktop.mjs   (needs a DISPLAY; uses fixtures.local.json "ext" user)
import fs from "fs"; import path from "path"; import os from "os"; import { fileURLToPath } from "url";
const here = path.dirname(fileURLToPath(import.meta.url));
import { tagFlow } from "./tags-flow.mjs";
const { chromium } = await import(path.join(process.env.PLAYWRIGHT_DIR || "/workspace/up/bw-oss/node_modules/playwright", "index.mjs"));
const DIR = process.env.KOMBOE_DESKTOP || "/workspace/up/bw-oss/apps/desktop/dist/linux-unpacked";
const WEB = process.env.KOMBOE_WEB || "https://localhost:8443"; const SHOTS = path.join(here, "../../docs/screenshots");
const fx = JSON.parse(fs.readFileSync(path.join(here, "fixtures.local.json")));
const rpath = path.join(here, "results.json"); const results = fs.existsSync(rpath) ? JSON.parse(fs.readFileSync(rpath)) : {};
const home = fs.mkdtempSync(path.join(os.tmpdir(), "komboe-desk-"));
import { spawn } from "child_process";
let app, proc; const PORT = 9333 + Math.floor(Math.random() * 500);
async function step(name, fn) { try { await fn(); results[name] = "passed"; console.log("PASS", name); }
  catch (e) { results[name] = "failed"; console.log("FAIL", name, String(e.message || e).replace(/\s+/g, " ").slice(0, 300)); } }
await step("desktop-launch", async () => {
  // Release fuses disable --inspect (Playwright's _electron), but Chromium's CDP port works, so attach over CDP.
  proc = spawn(path.join(DIR, "komboe"), ["--no-sandbox", "--ignore-certificate-errors", `--remote-debugging-port=${PORT}`],
    { env: { ...process.env, HOME: home, XDG_CONFIG_HOME: path.join(home, ".config") }, stdio: "ignore" });
  for (let i = 0; i < 60 && !app; i++) { await new Promise(r => setTimeout(r, 1000));
    app = await chromium.connectOverCDP(`http://127.0.0.1:${PORT}`).catch(() => null); }
  if (!app) throw new Error("no CDP endpoint");
  app.firstWindow = async () => { for (let i = 0; i < 60; i++) { const p = app.contexts().flatMap(c => c.pages()).find(p => !p.url().startsWith("devtools"));
    if (p) return p; await new Promise(r => setTimeout(r, 1000)); } throw new Error("no window"); };
  const w = await app.firstWindow(); await w.waitForLoadState("domcontentloaded"); if ((await w.title()) !== "Komboe") throw new Error("window title " + await w.title()); await w.locator("h1:visible", { hasText: "Log in to Komboe" }).first().waitFor({ timeout: 60000 });
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
  await w.getByText("Autofill test").filter({ visible: true }).first().waitFor({ timeout: 60000 }); await w.waitForTimeout(1500);
  await w.screenshot({ path: path.join(SHOTS, "desktop-vault.png") });
});
if (results["desktop-login"] === "passed") await step("tags-desktop", async () => {
  const w = await app.firstWindow(); w.setDefaultTimeout(30000);
  await tagFlow(w, "desk", "Autofill test", fs.existsSync("/tmp/komboe-web-tag.txt") ? fs.readFileSync("/tmp/komboe-web-tag.txt", "utf8") : null);
  await w.screenshot({ path: path.join(SHOTS, "tags-desktop.png") });
});
if (results["desktop-login"] === "passed") await step("templates-desktop", async () => {
  const w = await app.firstWindow(); w.setDefaultTimeout(30000);
  const { templateFlow } = await import("./templates-flow.mjs"); await templateFlow(w, "desk", async () => {
    const bs = w.getByRole("button", { name: "Add", exact: true }).filter({ visible: true });
    for (let i = 0; i < await bs.count(); i++) { const b = await bs.nth(i).boundingBox(); if (b && b.x > 300) { await bs.nth(i).click(); return; } }
    throw new Error("no header Add button"); });
  await w.screenshot({ path: path.join(SHOTS, "templates-desktop.png") });
});
if (results["desktop-login"] === "passed") await step("gpg-desktop", async () => {
  const w = await app.firstWindow(); w.setDefaultTimeout(30000);
  const { gpgFlow } = await import("./templates-flow.mjs"); await gpgFlow(w, "desk", async () => {
    const bs = w.getByRole("button", { name: "Add", exact: true }).filter({ visible: true });
    for (let i = 0; i < await bs.count(); i++) { const b = await bs.nth(i).boundingBox(); if (b && b.x > 300) { await bs.nth(i).click(); return; } }
    throw new Error("no header Add button"); });
  await w.screenshot({ path: path.join(SHOTS, "gpg-desktop.png") });
});
if (app) await app.close().catch(() => {}); if (proc) proc.kill();
await new Promise(r => setTimeout(r, 1500)); try { fs.rmSync(home, { recursive: true, force: true }); } catch {}
fs.writeFileSync(rpath, JSON.stringify(results, null, 1) + "\n");
