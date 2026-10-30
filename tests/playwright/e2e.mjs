// Komboe web vault + family console + extension E2E (Playwright library, system Chrome).
// Usage: node e2e.mjs   (env: KOMBOE_WEB=https://localhost:8443, PLAYWRIGHT_DIR, CHROME, KOMBOE_EXT_DIR)
import fs from "fs"; import path from "path"; import { fileURLToPath } from "url";
const here = path.dirname(fileURLToPath(import.meta.url));
const { chromium } = await import(path.join(process.env.PLAYWRIGHT_DIR || "/workspace/up/bw-oss/node_modules/playwright", "index.mjs"));
const WEB = process.env.KOMBOE_WEB || "https://localhost:8443";
const CHROME = process.env.CHROME || "/usr/bin/google-chrome";
const SHOTS = path.join(here, "../../docs/screenshots");
const fx = JSON.parse(fs.readFileSync(path.join(here, "fixtures.local.json")));
const results = {}; const notes = {};
const browser = await chromium.launch({ executablePath: CHROME, args: ["--no-sandbox"] });
const ctx = await browser.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1280, height: 820 } });
const shot = (p, name) => p.screenshot({ path: path.join(SHOTS, name + ".png") });
async function step(name, fn) {
  try { await fn(); results[name] = "passed"; console.log("PASS", name); }
  catch (e) { await p.screenshot({ path: `/tmp/fail-${name}.png` }).catch(() => {}); results[name] = "failed"; notes[name] = String(e.message || e).replace(/\s+/g, " ").slice(0, 300); console.log("FAIL", name, notes[name]); }
}
async function vaultLogin(p, u) {
  await p.goto(WEB + "/#/login"); await p.fill("#email", u.email); await p.getByRole("button", { name: /continue/i }).click();
  await p.fill("#masterPassword", u.pw); await p.getByRole("button", { name: "Log in", exact: true }).click();
  await p.waitForURL(/setup-extension|vault/, { timeout: 30000 });
  if (p.url().includes("setup-extension")) { await p.getByRole("button", { name: "Add it later" }).click(); await p.getByRole("link", { name: "Skip to web app" }).click(); }
  await p.waitForSelector("#newItemDropdown", { timeout: 30000 });
  const skip = p.getByRole("button", { name: "Skip", exact: true }); if (await skip.count()) await skip.click().catch(() => {});
}
const p = await ctx.newPage(); p.setDefaultTimeout(15000);

await step("login", async () => { await vaultLogin(p, fx.owner); await p.waitForTimeout(1500); await shot(p, "vault-home"); });

await step("item-crud", async () => {
  const name = "Komboe demo login";
  await p.click("#newItemDropdown"); await p.getByRole("menuitem", { name: /^login$/i }).click();
  await p.fill("input[formcontrolname=name]", name); await p.fill("input[formcontrolname=username]", "demo@example.com");
  await p.fill("input[formcontrolname=password]", "Correct-Horse-Battery-9"); await p.fill("input[formcontrolname=uri]", "https://example.com");
  await shot(p, "item-new"); await p.getByRole("button", { name: "Save", exact: true }).click();
  await p.waitForTimeout(2000); await p.keyboard.press("Escape"); await p.waitForTimeout(800);
  await p.getByText(name, { exact: true }).first().waitFor({ timeout: 15000 }); await shot(p, "vault-items");
  // edit
  await p.getByText(name, { exact: true }).first().click(); await p.waitForTimeout(1200);
  const edit = p.getByRole("button", { name: /^edit$/i }); if (await edit.count()) await edit.first().click();
  await p.fill("input[formcontrolname=name]", name + " (edited)"); await p.getByRole("button", { name: "Save", exact: true }).click();
  await p.waitForTimeout(2000); await p.keyboard.press("Escape"); await p.waitForTimeout(800);
  await p.getByText(name + " (edited)", { exact: true }).first().waitFor({ timeout: 15000 });
  // delete (to trash)
  await p.getByText(name + " (edited)", { exact: true }).first().click(); await p.waitForTimeout(1200);
  await p.getByRole("button", { name: /delete/i }).last().click(); await p.waitForTimeout(800);
  const yes = p.getByRole("button", { name: /^yes$/i }); if (await yes.count()) await yes.click();
  await p.waitForTimeout(2000); await p.keyboard.press("Escape").catch(() => {});
  if (await p.getByText(name + " (edited)", { exact: true }).count()) throw new Error("item still listed after delete");
});

await step("generator", async () => {
  await p.goto(WEB + "/#/tools/generator"); await p.waitForTimeout(3000);
  const close = p.locator("main").getByRole("button", { name: "Close" }); if (await close.count()) await close.first().click().catch(() => {});
  await shot(p, "generator-password");
  const val = async () => (await p.locator("main bit-color-password").first().innerText()).replace(/\s/g, "");
  const a1 = await val(); if (a1.length < 12) throw new Error("password too short: " + a1.length);
  await p.getByRole("button", { name: "Generate password" }).click(); await p.waitForTimeout(800);
  if ((await val()) === a1) throw new Error("regenerate did not change the password");
  await p.locator("main label[aria-label=Passphrase]").click(); await p.waitForTimeout(1200);
  if ((await val()).split("-").length < 3) throw new Error("passphrase not word-separated");
  await shot(p, "generator-passphrase");
  await p.locator("main label[aria-label=Username]").click(); await p.waitForTimeout(1200);
  if (!(await val())) throw new Error("no username generated"); await shot(p, "generator-username");
});

await step("alias-generator", async () => {
  await p.goto(WEB + "/#/tools/generator"); await p.waitForTimeout(2500);
  await p.locator("main label[aria-label=Username]").click(); await p.waitForTimeout(1000);
  await p.click("main bit-select >> nth=0 >> input"); await p.getByRole("option", { name: /forwarded email alias/i }).click(); await p.waitForTimeout(800);
  await p.click("main bit-select >> nth=1 >> input"); await p.getByRole("option", { name: "SimpleLogin" }).click(); await p.waitForTimeout(800);
  await p.fill("main input[formcontrolname=token]", fx.aliasKey); await p.fill("main input[formcontrolname=baseUrl]", WEB);
  await p.locator("main input[formcontrolname=baseUrl]").blur(); await p.waitForTimeout(800);
  const trust = p.getByRole("button", { name: "Trust URL" }); if (await trust.count()) { await trust.click(); await p.waitForTimeout(800); }
  await p.getByRole("button", { name: "Generate email" }).click();
  await p.waitForFunction(() => /@alias\.komboe\.localhost/.test(document.querySelector("main")?.innerText || ""), null, { timeout: 20000 });
  await p.fill("main input[formcontrolname=token]", "");  // do not leave the key visible in screenshots
  await shot(p, "generator-alias");
});

await step("send", async () => {
  await p.goto(WEB + "/#/sends"); await p.waitForTimeout(2500);
  const nb = p.getByRole("button", { name: /create/i }).first(); await nb.click(); await p.waitForTimeout(800);
  const t = p.getByRole("menuitem", { name: /^text$/i }); if (await t.count()) await t.click();
  await p.waitForTimeout(1500);
  await p.fill("input[formcontrolname=name]", "Wi-Fi password for guests");
  await p.fill("textarea[formcontrolname=text], textarea", "guest-network: Komboe-Guest-2026");
  await shot(p, "send-new"); await p.getByRole("button", { name: /^save$/i }).click(); await p.waitForTimeout(2500);
  await p.keyboard.press("Escape").catch(() => {}); await p.waitForTimeout(800);
  await p.getByText("Wi-Fi password for guests").first().waitFor({ timeout: 15000 }); await shot(p, "send-list");
});

await step("admin-console", async () => {
  await p.goto(WEB + `/#/organizations/${fx.orgId}/members`); await p.waitForTimeout(3500);
  await p.getByText(fx.kid.email).first().waitFor({ timeout: 15000 }); await shot(p, "org-members");
});

async function consoleLogin(cp, u) {
  await cp.goto(WEB + "/api/komboe/family-console"); await cp.fill("#email", u.email); await cp.fill("#password", u.pw);
  await cp.click("#loginForm button"); await cp.waitForSelector("#app:not([hidden])", { timeout: 30000 });
}
await step("org-family", async () => {
  const cp = await ctx.newPage(); await consoleLogin(cp, fx.owner);
  await cp.locator(".org", { hasText: "Rivera Family" }).getByRole("button", { name: "Open" }).click();
  await cp.waitForSelector("#members tbody tr"); const t = await cp.locator("#members").innerText();
  if (!t.includes(fx.kid.email) || !t.includes("No (encrypted)")) throw new Error("member row missing");
  await shot(cp, "family-console-admin");
  await cp.locator("#splits tr", { hasText: fx.kid.email }).getByRole("button", { name: "Approve" }).click();
  await cp.locator("#splits tr", { hasText: "approved" }).waitFor(); await shot(cp, "family-split-approved"); await cp.close();
});
await step("split-off", async () => {
  const c2 = await browser.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1280, height: 820 } }); const cp = await c2.newPage();
  await consoleLogin(cp, fx.kid); await cp.waitForSelector("#mine:not([hidden])"); await shot(cp, "family-split-member");
  cp.once("dialog", (d) => d.accept("Jordan's family"));
  await cp.getByRole("button", { name: "Create my family and move" }).click();
  await cp.locator(".org", { hasText: "Jordan's family" }).waitFor({ timeout: 30000 });
  if (await cp.locator(".org", { hasText: "Rivera Family" }).count()) throw new Error("still in old family");
  if (!(await cp.locator(".org", { hasText: "Jordan's family" }).innerText()).includes("Owner")) throw new Error("not owner of new family");
  await shot(cp, "family-split-done");
  // personal vault still there
  const vp = await c2.newPage(); await vaultLogin(vp, fx.kid); await vp.getByText("Game account").first().waitFor({ timeout: 15000 });
  await shot(vp, "family-split-member-vault"); await c2.close();
});
await browser.close();

const ext = process.env.KOMBOE_EXT_DIR;
const withTimeout = (ms, f) => async () => { let t; try { return await Promise.race([f(), new Promise((_, r) => (t = setTimeout(() => r(new Error("timeout " + ms + "ms")), ms)))]); } finally { clearTimeout(t); } };
if (ext && fs.existsSync(path.join(ext, "manifest.json"))) await step("extension-loads", withTimeout(60000, async () => {
  const ec = await chromium.launchPersistentContext(fs.mkdtempSync("/tmp/kext-"), { executablePath: CHROME, headless: true, ignoreHTTPSErrors: true,
    args: ["--no-sandbox", "--headless=new", "--disable-features=DisableLoadExtensionCommandLineSwitch", `--disable-extensions-except=${ext}`, `--load-extension=${ext}`], viewport: { width: 400, height: 640 } });
  let sw = ec.serviceWorkers()[0] || await ec.waitForEvent("serviceworker", { timeout: 20000 });
  const id = sw.url().split("/")[2]; const pp = await ec.newPage(); await pp.goto(`chrome-extension://${id}/popup/index.html`); await pp.waitForTimeout(4000);
  const body = await pp.evaluate(() => document.body.innerText); await pp.screenshot({ path: path.join(SHOTS, "extension-popup.png") });
  await ec.close(); if (!/Komboe/.test(body)) throw new Error("popup not rebranded: " + body.slice(0, 120));
}));
fs.writeFileSync(path.join(here, "results.json"), JSON.stringify(results, null, 2) + "\n");
fs.writeFileSync(path.join(here, "notes.json"), JSON.stringify(notes, null, 2) + "\n");
console.log("RESULTS", JSON.stringify(results)); process.exit(0);
