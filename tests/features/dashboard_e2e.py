#!/usr/bin/env python3
"""Browser end-to-end test for the Komboe vault dashboard (#105)."""
import hashlib
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from komboe.platform.crypto import dec, enc, master_key, password_hash, stretch  # noqa: E402
from komboe.platform.server import serve_in_thread  # noqa: E402

SECRET_NAME = "Northern Light Bank"
SECRET_PASSWORD = "s3cret-unique-northern-77"
MASTER = "Correct-Horse-Komboe-1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assert_crypto_matches_browser():
    """The dashboard's WebCrypto must decrypt a Python EncString and the reverse."""
    import json
    import subprocess
    email, password, plain = "ada@komboe.test", "dashboard-secret-pass", "vector-plain-text"
    mk = master_key(password, email, 600_000)
    key = stretch(mk)
    token = enc(plain.encode(), key)
    script = r"""
const fs = require("fs"); const vm = require("vm");
const ctx = { crypto: globalThis.crypto, TextEncoder, TextDecoder, btoa, atob, Uint8Array, console };
ctx.globalThis = ctx;
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(process.argv[2], "utf8"), ctx);
const spec = JSON.parse(process.argv[3]);
(async () => {
  const C = ctx.KomboeCrypto;
  const mk = await C.pbkdf2(spec.password, C.utf8(spec.email), 600000, 32);
  const hash = await C.passwordHash(mk, spec.password);
  const stretched = await C.stretch(mk);
  const opened = new TextDecoder().decode(await C.dec(spec.token, stretched));
  if (opened !== spec.plain) throw new Error("js could not open python ciphertext: " + opened);
  const again = await C.enc(spec.plain, stretched);
  const out = { hash, again };
  fs.writeFileSync(process.argv[4], JSON.stringify(out));
})().catch((e) => { console.error(e); process.exit(1); });
"""
    out = tempfile.NamedTemporaryFile(delete=False)
    out.close()
    runner = tempfile.NamedTemporaryFile("w", suffix=".js", delete=False)
    runner.write(script)
    runner.close()
    spec = json.dumps({"email": email, "password": password, "token": token, "plain": plain})
    proc = subprocess.run(
        ["node", runner.name, str(ROOT / "komboe/platform/dashboard/crypto.js"), spec, out.name],
        capture_output=True, text=True, timeout=60,
    )
    if proc.returncode != 0:
        raise SystemExit(proc.stdout + proc.stderr)
    got = json.loads(Path(out.name).read_text())
    if got["hash"] != password_hash(mk, password):
        raise SystemExit("password hash mismatch between Python and the dashboard")
    if dec(got["again"], key).decode() != plain:
        raise SystemExit("python could not open dashboard ciphertext")
    os.unlink(runner.name)
    os.unlink(out.name)


def assert_sources_clean():
    for rel in ("index.html", "app.css", "app.js", "crypto.js"):
        text = (ROOT / "komboe/platform/dashboard" / rel).read_text(errors="replace").lower()
        for banned in ("bitwarden", "proton"):
            if banned in text:
                raise SystemExit(f"{rel} contains {banned}")


def main():
    assert_sources_clean()
    assert_crypto_matches_browser()
    db_dir = tempfile.mkdtemp(prefix="kdash-")
    db_path = os.path.join(db_dir, "dash.sqlite3")
    httpd, _db = serve_in_thread(db_path)
    port = httpd.server_address[1]
    base = f"http://127.0.0.1:{port}"
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise SystemExit("playwright is required for the dashboard E2E") from exc
    light = ROOT / "branding/logo/variants/komboe-light-transparent.png"
    dark = ROOT / "branding/logo/variants/komboe-dark-transparent.png"
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.emulate_media(color_scheme="light")
        page.goto(base + "/", wait_until="networkidle")
        page.wait_for_function("document.fonts.check('600 28px Sora')")
        html = page.content().lower()
        if "bitwarden" in html or "proton" in html:
            raise SystemExit("dashboard page contains disallowed branding")
        font = page.eval_on_selector("[data-testid=wordmark]", "el => getComputedStyle(el).fontFamily")
        if "sora" not in font.lower():
            raise SystemExit(f"wordmark font is {font}")
        logo_bytes = page.evaluate("async () => { const r = await fetch(document.querySelector('[data-testid=logo]').src); return [...new Uint8Array(await r.arrayBuffer())]; }")
        if hashlib.sha256(bytes(logo_bytes)).hexdigest() != sha256(light):
            raise SystemExit("light logo bytes differ from the locked padlock-K variant")
        page.fill("[data-testid=email]", "ada@komboe.test")
        page.fill("[data-testid=password]", MASTER)
        page.click("[data-testid=create-account]")
        page.wait_for_selector("[data-testid=sidebar]", timeout=30000)
        for name in ("sidebar", "list", "detail"):
            box = page.locator(f"[data-testid={name}]").bounding_box()
            if not box or box["width"] < 80:
                raise SystemExit(f"{name} pane missing")
        page.click("[data-testid=new-item]")
        page.fill("[data-testid=item-name]", SECRET_NAME)
        page.fill("[data-testid=item-username]", "ada")
        page.fill("[data-testid=item-password]", SECRET_PASSWORD)
        page.fill("[data-testid=item-uri]", "https://north.example")
        page.click("[data-testid=save-item]")
        page.wait_for_selector(f"[data-testid=detail-name]:text('{SECRET_NAME}')")
        if page.inner_text("[data-testid=detail-password]") != SECRET_PASSWORD:
            raise SystemExit("password did not round-trip in the vault pane")
        light_bg = page.evaluate("() => getComputedStyle(document.body).backgroundColor")
        page.click("[data-testid=theme-toggle]")
        page.wait_for_function("document.documentElement.dataset.theme === 'dark'")
        dark_bg = page.evaluate("() => getComputedStyle(document.body).backgroundColor")
        if light_bg == dark_bg:
            raise SystemExit("theme toggle did not change the background")
        dark_logo = page.evaluate("async () => { const r = await fetch(document.querySelector('[data-testid=logo]').src); return [...new Uint8Array(await r.arrayBuffer())]; }")
        if hashlib.sha256(bytes(dark_logo)).hexdigest() != sha256(dark):
            raise SystemExit("dark logo bytes differ from the locked padlock-K variant")
        page.reload(wait_until="networkidle")
        page.wait_for_selector(f"text={SECRET_NAME}")
        if page.evaluate("() => document.documentElement.dataset.theme") != "dark":
            raise SystemExit("dark theme did not persist")
        page.click("[data-testid=search]")
        page.fill("[data-testid=search]", "northern")
        page.wait_for_selector(f"text={SECRET_NAME}")
        page.fill("[data-testid=search]", "no-such-item")
        page.wait_for_selector("text=Nothing matches")
        browser.close()
    raw = Path(db_path).read_bytes()
    for secret in (SECRET_NAME, SECRET_PASSWORD, MASTER):
        if secret.encode() in raw:
            raise SystemExit(f"plaintext {secret!r} found in the server database")
    httpd.shutdown()
    print("DASHBOARD E2E PASS")


if __name__ == "__main__":
    main()
