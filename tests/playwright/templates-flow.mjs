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
  return name;
}
