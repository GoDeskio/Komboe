// Open every link from recent Mailpit mail in Chromium (LOCAL/TEST ONLY). Usage: node email_links.mjs [maxMessages]
import path from "path";
const { chromium } = await import(path.join(process.env.PLAYWRIGHT_DIR, "index.mjs"));
const MP = process.env.MAILPIT || "http://127.0.0.1:8025", N = +(process.argv[2] || 150);
const list = (await (await fetch(`${MP}/api/v1/messages?limit=${N}`)).json()).messages;
const links = new Map();
for (const m of list) {
  const full = await (await fetch(`${MP}/api/v1/message/${m.ID}`)).json();
  for (const [, u] of (full.HTML || "").matchAll(/href="([^"]+)"/g)) {
    const url = u.replace(/&amp;/g, "&"); if (url.startsWith("mailto:")) continue;
    const key = url.replace(/[?#].*$/, "") + "|" + (url.match(/#\/[^?]*/) || [""])[0];
    if (!links.has(key)) links.set(key, { url, subject: m.Subject });
  }
}
const b = await chromium.launch({ executablePath: process.env.CHROME || "/usr/bin/google-chrome", args: ["--no-sandbox"] });
const ctx = await b.newContext({ ignoreHTTPSErrors: true }); let bad = 0;
for (const { url, subject } of links.values()) {
  const local = /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?(\/|$)/.test(url);
  if (!local) { console.log("SKIP(external)", url.replace(/\?.*/, ""), "|", subject); continue; }
  const p = await ctx.newPage(); let st = 0, txt = "";
  try { const r = await p.goto(url, { waitUntil: "domcontentloaded", timeout: 30000 }); st = r ? r.status() : 0;
        await p.waitForTimeout(4000); txt = (await p.title()) + " " + (await p.evaluate(() => document.body.innerText)).replace(/\s+/g, " ").slice(0, 120); }
  catch (e) { txt = String(e.message).slice(0, 120); }
  const ok = st >= 200 && st < 400 && /Komboe/i.test(txt) && !/bitwarden|vaultwarden/i.test(txt);
  if (!ok) bad++; console.log(ok ? "OK  " : "BAD ", st, url.replace(/(token|code)=[^&]+/g, "$1=…").slice(0, 110), "|", subject, "|", txt);
  await p.close();
}
console.log("LINKS", links.size, "BAD", bad); await b.close(); process.exit(bad ? 1 : 0);
