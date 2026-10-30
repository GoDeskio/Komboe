// Komboe web vault + family console + extension E2E (Playwright library, system Chrome for the vault, bundled Chromium for the extension).
// Usage: node e2e.mjs   (env: KOMBOE_WEB=https://localhost:8443, PLAYWRIGHT_DIR, CHROME, KOMBOE_EXT_DIR)
import fs from "fs"; import path from "path"; import crypto from "crypto"; import { fileURLToPath } from "url";
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

const ext = process.env.KOMBOE_EXT_DIR;
const withTimeout = (ms, f) => async () => { let t; try { return await Promise.race([f(), new Promise((_, r) => (t = setTimeout(() => r(new Error("timeout " + ms + "ms")), ms)))]); } finally { clearTimeout(t); } };
// Vault health reports + password-protected export, as a separate user seeded with weak/reused/http items.
const hctx = await browser.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1280, height: 820 }, acceptDownloads: true });
const hp = await hctx.newPage(); hp.setDefaultTimeout(30000);
let healthIn = false;
try { await vaultLogin(hp, fx.health); healthIn = true; } catch (e) { notes["health-login"] = String(e.message || e).slice(0, 200); }
const REPORTS = { "report-weak": ["weak-passwords-report", /Weak reused A.*Weak reused B/s, /Strong unique/],
  "report-reused": ["reused-passwords-report", /Reused 2 times/, /Strong unique/],
  "report-unsecured": ["unsecured-websites-report", /We found 1 items.*Weak reused A/s, /Weak reused B|Strong unique/],
  "report-inactive-2fa": ["inactive-two-factor-report", /Weak reused B/, null],   // github.com via 2fa.directory (public)
  "report-exposed": ["exposed-passwords-report", /Weak reused A.*Exposed/s, /Strong unique/] };   // HIBP k-anonymity range API
for (const [name, [route, must, mustNot]] of Object.entries(REPORTS)) if (healthIn) await step(name, async () => {
  await hp.goto(WEB + "/#/reports/" + route); await hp.waitForTimeout(3000);
  const chk = hp.locator("main").getByRole("button", { name: /^check/i }); if (await chk.count()) { await chk.first().click(); }
  await hp.waitForFunction((re) => new RegExp(re, "s").test(document.querySelector("main")?.innerText || ""), must.source, { timeout: 30000 });
  const txt = await hp.locator("main").innerText(); if (mustNot && mustNot.test(txt)) throw new Error("report lists an item it should not");
  await hp.screenshot({ path: path.join(SHOTS, name + ".png") });
});
if (healthIn) await step("export-encrypted", async () => {
  await hp.goto(WEB + "/#/tools/export"); await hp.waitForTimeout(3000);
  const sk = hp.locator(".cdk-overlay-container button", { hasText: "Skip" }); if (await sk.count()) await sk.first().click();
  await hp.selectOption("select[formcontrolname=format]", { label: ".json (Encrypted)" });
  await hp.getByText("Password protected").click();
  const FP = "Export-Pass-123!"; await hp.fill("input[formcontrolname=filePassword]", FP); await hp.fill("input[formcontrolname=confirmFilePassword]", FP);
  const dl = hp.waitForEvent("download", { timeout: 60000 });
  await hp.getByRole("button", { name: "Export", exact: true }).click();
  await hp.locator("input#masterPassword").fill(fx.health.pw); await hp.getByRole("button", { name: "Continue" }).click();
  const f = "/tmp/komboe-export-test.json"; await (await dl).saveAs(f); const j = JSON.parse(fs.readFileSync(f, "utf8")); fs.unlinkSync(f);
  if (!j.passwordProtected || /Weak reused/.test(j.data)) throw new Error("export is not password-protected ciphertext");
  const names = decryptExport(j, FP).items.map((i) => i.name).sort().join(",");
  if (names !== "Strong unique,Weak reused A,Weak reused B") throw new Error("decrypted export mismatch: " + names);
});
await hctx.close();

// Decrypt a Bitwarden-format password-protected export independently (PBKDF2-SHA256 -> HKDF-expand enc/mac -> AES-256-CBC + HMAC).
function decryptExport(j, pw) {
  const key = crypto.pbkdf2Sync(pw, j.salt, j.kdfIterations, 32, "sha256");
  const ex = (info) => crypto.createHmac("sha256", key).update(Buffer.concat([Buffer.from(info), Buffer.from([1])])).digest();
  const enc = ex("enc"), mac = ex("mac"); const [t, rest] = j.data.split(".");
  if (j.kdfType !== 0 || t !== "2") throw new Error("unexpected kdf/enc type");
  const [iv, ct, m] = rest.split("|").map((x) => Buffer.from(x, "base64"));
  if (!crypto.timingSafeEqual(crypto.createHmac("sha256", mac).update(Buffer.concat([iv, ct])).digest(), m)) throw new Error("bad MAC");
  const d = crypto.createDecipheriv("aes-256-cbc", enc, iv); return JSON.parse(Buffer.concat([d.update(ct), d.final()]).toString());
}

await browser.close();

// Extension: Playwright's bundled Chromium (branded Chrome ignores --load-extension). A desktop-Chrome UA is forced
// because the extension treats "HeadlessChrome" as Safari and the popup never finishes loading.
const UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36";
if (ext && fs.existsSync(path.join(ext, "manifest.json"))) {
  let ec, pp, id;
  await step("extension-loads", withTimeout(120000, async () => {
    ec = await chromium.launchPersistentContext(fs.mkdtempSync("/tmp/kext-"), { channel: "chromium", headless: true, ignoreHTTPSErrors: true,
      args: ["--no-sandbox", `--user-agent=${UA}`, `--disable-extensions-except=${ext}`, `--load-extension=${ext}`], viewport: { width: 400, height: 640 } });
    const sw = ec.serviceWorkers()[0] || await ec.waitForEvent("serviceworker", { timeout: 20000 });
    id = sw.url().split("/")[2]; pp = await ec.newPage(); pp.setDefaultTimeout(30000); await pp.waitForTimeout(8000);
    for (let i = 0; i < 4; i++) { await pp.goto(`chrome-extension://${id}/popup/index.html`);
      try { await pp.waitForSelector("#default-password-manager-prompt_button_skip-for-now, #email", { timeout: 20000 }); break; } catch { /* retry */ } }
    const body = await pp.evaluate(() => document.body.innerText); await pp.screenshot({ path: path.join(SHOTS, "extension-popup.png") });
    if (!/Komboe/.test(body)) throw new Error("popup not rebranded: " + body.slice(0, 120));
  }));
  if (results["extension-loads"] === "passed") await step("extension-login", withTimeout(150000, async () => {
    const sk = pp.locator("#default-password-manager-prompt_button_skip-for-now"); if (await sk.count()) await sk.click();
    for (let i = 0; i < 5 && !(await pp.getByText("Accessing").count()); i++) {
      await pp.waitForTimeout(2000); const li = pp.locator("a, button").filter({ hasText: /^\s*Log in\s*$/ });
      if (await li.count()) await li.last().click().catch(() => {}); await pp.waitForTimeout(3000); }
    try { await pp.getByText("Accessing").first().waitFor({ timeout: 20000 }); }
    catch (e) { await pp.screenshot({ path: "/tmp/fail-ext-login.png" }); throw new Error("no server picker: " + (await pp.evaluate(() => document.body.innerText)).replace(/\s+/g, " ").slice(0, 200)); }
    await pp.locator("button", { hasText: /bitwarden\.com|Choose your Komboe server/ }).first().click(); await pp.locator("button", { hasText: "self-hosted" }).first().click();
    await pp.getByLabel("Server URL").fill(WEB); await pp.getByRole("button", { name: "Save" }).click(); await pp.waitForTimeout(1500);
    await pp.fill("#email", fx.ext.email); await pp.getByRole("button", { name: "Continue" }).click();
    await pp.fill("#masterPassword", fx.ext.pw); await pp.getByRole("button", { name: "Log in", exact: true }).click();
    await pp.getByText("Autofill test").first().waitFor({ timeout: 60000 }); await pp.screenshot({ path: path.join(SHOTS, "extension-vault.png") });
  }));
  if (results["extension-login"] === "passed") await step("extension-autofill", withTimeout(90000, async () => {
    await ec.route("https://autofill.komboe.test/**", (r) => r.fulfill({ contentType: "text/html", body:
      '<!doctype html><title>Login</title><form><label>Email <input id="u" type="email" autocomplete="username"></label>' +
      '<label>Password <input id="p" type="password" autocomplete="current-password"></label><button>Sign in</button></form>' }));
    const tp = await ec.newPage(); await tp.setViewportSize({ width: 1000, height: 700 });
    await tp.goto("https://autofill.komboe.test/login"); await tp.waitForTimeout(3000); await tp.click("#u"); await tp.waitForTimeout(3000);
    await tp.screenshot({ path: path.join(SHOTS, "extension-inline-menu.png") });
    for (let i = 0; i < 3 && !(await tp.inputValue("#u")); i++) { await tp.mouse.click(150, 60); await tp.waitForTimeout(2500); }
    const u = await tp.inputValue("#u"), pw = await tp.inputValue("#p");
    if (u !== "auto@komboe.test" || pw !== "Autofill-Pass-1") throw new Error(`autofill got user=${u} pwlen=${pw.length}`);
  }));
  if (ec) await ec.close().catch(() => {});
}
fs.writeFileSync(path.join(here, "results.json"), JSON.stringify(results, null, 2) + "\n");
fs.writeFileSync(path.join(here, "notes.json"), JSON.stringify(notes, null, 2) + "\n");
console.log("RESULTS", JSON.stringify(results)); process.exit(0);
