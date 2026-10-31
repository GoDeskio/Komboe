// Komboe item templates in a real client: Wi-Fi and Bookmark appear on the new-item menu, save, and reopen with their values.
import fs from "fs";
export const SECRETS = "/tmp/komboe-template-secrets.txt";
export async function templateFlow(p, client, openMenu) {
  const rnd = Math.random().toString(36).slice(2, 8);
  const menu = [];
  await openMenu(); await p.waitForTimeout(800); await p.screenshot({ path: `/tmp/menu-${client}.png` });
  menu.push(...(await p.locator("[role=menuitem]").filter({ visible: true }).allInnerTexts()).map(s => s.trim()));
  for (const want of ["Wi-Fi", "Bookmark", "Passport", "Bank account", "License"])
    if (!menu.some(m => m.toLowerCase().includes(want.toLowerCase()))) throw new Error(`${client}: new-item menu lacks ${want}: ${menu.filter(Boolean).slice(0, 30).join("|")}`);
  // Wi-Fi: create, eye-toggle reveals the password, save.
  await p.locator("[role=menuitem]").filter({ visible: true }).filter({ hasText: "Wi-Fi" }).first().click();
  const name = `${client}-wifi-${rnd}`, secret = `wifi-pw-${rnd}`; fs.appendFileSync(SECRETS, secret + "\n");
  await p.getByLabel("Item name").filter({ visible: true }).first().fill(name);
  await p.getByLabel("Network name (SSID)").or(p.getByLabel("SSID")).filter({ visible: true }).first().fill(`ssid-${rnd}`);
    const field = p.locator("[data-testid=wifi-password]").filter({ visible: true }).first();
  await field.fill(secret);
  const eye = p.locator("[data-testid=toggle-wifi-password]").filter({ visible: true }).first();
  await eye.click(); await p.waitForTimeout(300);
  if (await field.getAttribute("type") !== "text") throw new Error(`${client}: eye toggle did not reveal the password`);
  if (await field.inputValue() !== secret) throw new Error(`${client}: revealed value mismatch`);
  await eye.click(); await p.waitForTimeout(300);
  if (await field.getAttribute("type") !== "password") throw new Error(`${client}: eye toggle did not re-hide the password`);
  await p.getByRole("button", { name: "Save", exact: true }).filter({ visible: true }).first().click(); await p.waitForTimeout(2500);
  await p.getByText(name).filter({ visible: true }).first().waitFor({ timeout: 20000 });
  // Bookmark: create from the same menu, save, reopen and read the URL back.
  await openMenu(); await p.waitForTimeout(800);
  await p.locator("[role=menuitem]").filter({ visible: true }).filter({ hasText: "Bookmark" }).first().click();
  const bname = `${client}-bm-${rnd}`, burl = `https://bm-${rnd}.example.test/`; fs.appendFileSync(SECRETS, burl + "\n");
  await p.getByLabel("Item name").filter({ visible: true }).first().fill(bname);
  await p.locator("[data-testid=bookmark-url]").filter({ visible: true }).first().fill(burl);
  await p.getByRole("button", { name: "Save", exact: true }).filter({ visible: true }).first().click(); await p.waitForTimeout(2500);
  const row = p.getByText(bname).filter({ visible: true }).first(); await row.waitFor({ timeout: 20000 });
  if (!(await p.locator("[data-testid=bookmark-url]").filter({ visible: true }).count())) { await row.click(); await p.waitForTimeout(1500); }
  const got = await p.locator("[data-testid=bookmark-url]").filter({ visible: true }).first().inputValue();
  if (got !== burl) throw new Error(`${client}: bookmark URL reopened as ${got}`);
  return name;
}

// GPG key item: create, eye toggles reveal private key (textarea, text-security) and passphrase, save, reopen, newlines kept.
async function hidden(loc) {
  return loc.evaluate(el => el.tagName === "TEXTAREA" ? getComputedStyle(el).webkitTextSecurity !== "none" : el.type === "password");
}
export async function gpgFlow(p, client, openMenu) {
  const rnd = Math.random().toString(36).slice(2, 8);
  const priv = `-----BEGIN PGP PRIVATE KEY BLOCK-----\n\n${client}-gpg-priv-${rnd}\nline-two-${rnd}\n-----END PGP PRIVATE KEY BLOCK-----`;
  const pass = `${client}-gpg-pass-${rnd}`; fs.appendFileSync(SECRETS, `${client}-gpg-priv-${rnd}\n${pass}\n`);
  await openMenu(); await p.waitForTimeout(800);
  await p.locator("[role=menuitem]").filter({ visible: true }).filter({ hasText: "GPG key" }).first().click();
  const name = `${client}-gpg-${rnd}`;
  await p.getByLabel("Item name").filter({ visible: true }).first().fill(name);
  const f = id => p.locator(`[data-testid=${id}]`).filter({ visible: true }).first();
  await f("gpg-key-id").fill("A1B2C3D4");
  await f("gpg-private-key").fill(priv);
  await f("gpg-passphrase").fill(pass);
  for (const [id, eye, val] of [["gpg-private-key", "toggle-gpg-private-key", priv], ["gpg-passphrase", "toggle-gpg-passphrase", pass]]) {
    if (!(await hidden(f(id)))) throw new Error(`${client}: ${id} not masked by default`);
    await f(eye).click(); await p.waitForTimeout(300);
    if (await hidden(f(id))) throw new Error(`${client}: ${eye} did not reveal`);
    if (await f(id).inputValue() !== val) throw new Error(`${client}: ${id} value mismatch`);
    await f(eye).click(); await p.waitForTimeout(300);
    if (!(await hidden(f(id)))) throw new Error(`${client}: ${eye} did not re-hide`);
  }
  await p.getByRole("button", { name: "Save", exact: true }).filter({ visible: true }).first().click(); await p.waitForTimeout(2500);
  const row = p.getByText(name).filter({ visible: true }).first(); await row.waitFor({ timeout: 20000 });
  if (!(await p.locator("[data-testid=gpg-private-key]").filter({ visible: true }).count())) { await row.click(); await p.waitForTimeout(1500); }
  const got = await f("gpg-private-key").inputValue();
  if (got !== priv) throw new Error(`${client}: GPG private key reopened changed (${JSON.stringify(got.slice(0, 60))})`);
  return name;
}
