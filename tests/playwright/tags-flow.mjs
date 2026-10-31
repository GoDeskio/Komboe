// Shared Komboe tags flow for the web vault, extension popup, and desktop app (the <komboe-tags> panel).
// Tag names it creates are appended to /tmp/komboe-tag-names.txt so the run can check the server DB holds none of them.
import fs from "fs";
export const NAMES = "/tmp/komboe-tag-names.txt";
const rnd = () => Math.random().toString(36).slice(2, 8);
async function tagged(p, tag) {
  await p.locator("[data-testid=komboe-tags] [data-testid=tag]", { hasText: tag }).first().click();
  return (await p.locator("[data-testid=komboe-tags] [data-testid=tagged-item]").allInnerTexts()).map((s) => s.trim());
}
async function create(p, tag) {
  fs.appendFileSync(NAMES, tag + "\n");
  await p.fill("[data-testid=komboe-tags] [data-testid=tag-name]", tag); await p.click("[data-testid=komboe-tags] [data-testid=tag-create]");
  await p.locator("[data-testid=komboe-tags] [data-testid=tag]", { hasText: tag }).first().waitFor({ timeout: 20000 });
}
async function apply(p, tag, item, btn = "tag-assign") {
  await p.locator("[data-testid=komboe-tags] [data-testid=tag]", { hasText: tag }).first().click();
  await p.selectOption("[data-testid=komboe-tags] [data-testid=tag-item]", { label: item });
  await p.click(`[data-testid=komboe-tags] [data-testid=${btn}]`); await p.waitForTimeout(1500);
  const err = p.locator("[data-testid=komboe-tags] [data-testid=tag-error]"); if (await err.count()) throw new Error("tag error: " + await err.innerText());
}
// Full flow: two tags on one item, both kept; remove one; delete it. Optionally verify a tag made by another client is visible here.
export async function tagFlow(p, client, item, seenTag) {
  await p.locator("[data-testid=komboe-tags]").first().waitFor({ timeout: 30000 });
  if (seenTag) { const got = await tagged(p, seenTag); if (!got.includes(item)) throw new Error(`${client}: tag "${seenTag}" from another client not shown on ${item}: ${got}`); }
  const a = `${client}-A-${rnd()}`, b = `${client}-B-${rnd()}`;
  await create(p, a); await create(p, b);
  await apply(p, a, item); await apply(p, b, item);
  if (!(await tagged(p, a)).includes(item)) throw new Error(`${client}: applying a second tag dropped the first`);
  if (!(await tagged(p, b)).includes(item)) throw new Error(`${client}: second tag not applied`);
  await apply(p, b, item, "tag-unassign");
  if ((await tagged(p, b)).includes(item)) throw new Error(`${client}: remove tag did not remove`);
  if (!(await tagged(p, a)).includes(item)) throw new Error(`${client}: remove tag removed the wrong tag`);
  await p.locator("[data-testid=komboe-tags] [data-testid=tag]", { hasText: b }).first().click();
  await p.click("[data-testid=komboe-tags] [data-testid=tag-delete]"); await p.waitForTimeout(1500);
  if (await p.locator("[data-testid=komboe-tags] [data-testid=tag]", { hasText: b }).count()) throw new Error(`${client}: delete tag did not delete`);
  return a;
}
