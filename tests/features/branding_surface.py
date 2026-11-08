#!/usr/bin/env python3
"""User-facing Komboe branding regression.

Scans the client source for upstream commercial links and the Bitwarden shield
in templates, checks the empty-vault illustration and favicon against the
Komboe kit, inventories web routes, and screenshots a signed-in vault fixture
built from those real assets.

This does not boot the Angular web vault. The fixture renders the same mark,
empty-state SVG, and link targets the app now uses. Login-only checks are not
treated as coverage of the signed-in vault.
"""
import hashlib
import os
import re
import shutil
import subprocess
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CLIENTS = os.path.join(ROOT, "clients", "upstream")
OUT = os.environ.get("KOMBOE_BRANDING_OUT", "/tmp/komboe-branding-fixture")

OWNED = {
    "https://github.com/GoDeskio/Komboe",
    "https://github.com/GoDeskio/Komboe/issues",
    "https://github.com/GoDeskio/Komboe/tree/main/docs",
    "https://github.com/GoDeskio/Komboe/tree/main/mobile",
    "https://github.com/GoDeskio/Komboe/blob/main/docs/BROWSER-EXTENSIONS.md",
    "https://github.com/GoDeskio/Komboe/blob/main/apps/web-marketing/terms.html",
    "https://github.com/GoDeskio/Komboe/blob/main/apps/web-marketing/privacy.html",
    "https://github.com/GoDeskio/Komboe/blob/main/NOTICE",
}

# Not user-facing product links. Protocol hosts, fixtures, and attribution comments stay.
ALLOW_FILES = {
    "libs/common/src/platform/services/default-environment.service.ts",
    "libs/common/src/platform/services/default-environment.service.spec.ts",
    "libs/common/src/models/domain/domain-service.ts",
    "libs/common/src/autofill/utils/index.spec.ts",
    "libs/angular/src/billing/services/premium-interest/premium-interest-state.service.abstraction.ts",
    "apps/web/src/app/billing/payment/components/add-account-credit-dialog.component.ts",
    "apps/web/src/connectors",
}
ALLOW_SNIPPETS = (
    "webauthn-callback",
    "duo-callback",
    "paypal-banner",
    "map-the-web",
    "fillassist.bitwarden.com",
)

COMMERCIAL = re.compile(
    r"https://(?:www\.)?bitwarden\.com/[^\s\"'`)<]+"
    r"|https://chromewebstore\.google\.com/detail/[^\s\"'`)<]*"
    r"|https://chrome\.google\.com/webstore/detail/[^\s\"'`)<]*"
    r"|https://addons\.mozilla\.org/[^\s\"'`)<]*bitwarden[^\s\"'`)<]*"
    r"|https://addons\.opera\.com/[^\s\"'`)<]*bitwarden[^\s\"'`)<]*"
    r"|https://apps\.apple\.com/[^\s\"'`)<]*bitwarden[^\s\"'`)<]*"
    r"|https://itunes\.apple\.com/[^\s\"'`)<]*bitwarden[^\s\"'`)<]*"
    r"|https://play\.google\.com/store/apps/[^\s\"'`)<]*bitwarden[^\s\"'`)<]*"
    r"|https://blog\.bitwarden\.com[^\s\"'`)<]*"
    r"|https://twitter\.com/bitwarden[^\s\"'`)<]*"
    r"|https://www\.facebook\.com/bitwarden/?"
    r"|https://fosstodon\.org/@bitwarden[^\s\"'`)<]*"
    r"|https://github\.com/bitwarden(?:/[^\s\"'`)<]*)?"
)


def rel(path):
    return os.path.relpath(path, CLIENTS)


def allowed(path, snippet):
    r = rel(path)
    if any(r.startswith(a) or a in r for a in ALLOW_FILES):
        return True
    return any(s in snippet for s in ALLOW_SNIPPETS)


def scan():
    hits = []
    shields = []
    for dirpath, dirnames, filenames in os.walk(CLIENTS):
        dirnames[:] = [d for d in dirnames if d not in ("node_modules", "locales")]
        for fn in filenames:
            if not fn.endswith((".html", ".ts", ".json")) or fn.endswith(".stories.ts"):
                continue
            path = os.path.join(dirpath, fn)
            if "connectors" in path.split(os.sep):
                continue
            text = open(path, encoding="utf-8", errors="ignore").read()
            if fn.endswith(".html") and "bwi-bitwarden-shield" in text:
                shields.append(rel(path))
            lines = text.splitlines()
            for m in COMMERCIAL.finditer(text):
                snippet = m.group(0)
                if allowed(path, snippet):
                    continue
                line_no = text[: m.start()].count("\n")
                line_text = lines[line_no] if line_no < len(lines) else ""
                code = line_text.split("//", 1)[0]
                stripped = line_text.lstrip()
                if snippet not in code or stripped.startswith(("*", "/*", "<!--")):
                    continue
                hits.append(f"{rel(path)}:{line_no + 1}: {snippet[:140]}")
    return hits, shields


def favicons():
    pairs = [
        ("apps/web/src/favicon.ico", "brand/komboe-kit/favicons/favicon.ico"),
        ("apps/web/src/images/icons/favicon-32x32.png", "brand/komboe-kit/favicons/favicon-32x32.png"),
        ("apps/web/src/images/icons/favicon-16x16.png", "brand/komboe-kit/favicons/favicon-16x16.png"),
        ("apps/web/src/images/icons/favicon.svg", "brand/komboe-kit/favicons/favicon.svg"),
        ("apps/web/src/images/komboe-mark.svg", "brand/komboe-kit/favicons/favicon.svg"),
        ("apps/web/src/images/icons/android-chrome-192x192.png", "brand/komboe-kit/favicons/android-chrome-192x192.png"),
        ("apps/web/src/images/icons/android-chrome-512x512.png", "brand/komboe-kit/favicons/android-chrome-512x512.png"),
        ("apps/web/src/images/icons/apple-touch-icon.png", "brand/komboe-kit/favicons/apple-touch-icon.png"),
        ("apps/web/src/images/icons/maskable-icon-512x512.png", "brand/komboe-kit/favicons/maskable-icon-512x512.png"),
    ]
    bad = []
    for dest, src in pairs:
        d = os.path.join(CLIENTS, dest)
        s = os.path.join(ROOT, src)
        if hashlib.sha256(open(d, "rb").read()).digest() != hashlib.sha256(open(s, "rb").read()).digest():
            bad.append(dest)
    return bad


def empty_state():
    text = open(os.path.join(CLIENTS, "libs/assets/src/svg/svgs/item-types.ts"), encoding="utf-8").read()
    assert "komboe-item-types-bg" in text, "empty vault illustration is not the Komboe mark"
    assert "0 18.75 150 112.5" not in text, "upstream item-types illustration is still exported"
    assert 'aria-label="Komboe"' in text


def import_formats_kept():
    text = open(os.path.join(CLIENTS, "libs/importer/src/models/import-options.ts"), encoding="utf-8").read()
    assert 'id: "bitwardenjson"' in text or "bitwardenjson" in text or "bitwarden" in text.lower()
    # Compatibility format names stay. Only the instruction URLs moved.
    assert "bitwarden.com/help/import" not in text


def routes():
    found = []
    for dirpath, _, filenames in os.walk(os.path.join(CLIENTS, "apps/web/src")):
        for fn in filenames:
            if "routing" not in fn and fn != "oss-routing.module.ts":
                continue
            path = os.path.join(dirpath, fn)
            text = open(path, encoding="utf-8").read()
            for m in re.finditer(r"""path:\s*["']([^"']+)["']""", text):
                found.append((rel(path), m.group(1)))
    needed = {
        "login",
        "register",
        "vault",
        "settings",
        "tools",
        "reports",
        "about",
        "recover",
        "send",
    }
    paths = {p for _, p in found}
    # Nested route segments. Also accept full paths that contain the name.
    blob = "\n".join(p for _, p in found)
    missing = [n for n in sorted(needed) if n not in blob and not any(n in p for p in paths)]
    return found, missing


def live_urls():
    bad = []
    for url in sorted(OWNED):
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=12) as resp:
                if resp.status >= 400:
                    bad.append(f"{resp.status} {url}")
        except Exception as exc:  # noqa: BLE001 - report the destination, do not invent a fallback
            bad.append(f"{exc.__class__.__name__} {url}")
    return bad


def dashboard_contract():
    vault = open(
        os.path.join(CLIENTS, "apps/web/src/app/vault/individual-vault/vault.component.html"),
        encoding="utf-8",
    ).read()
    nxt = open(
        os.path.join(CLIENTS, "apps/web/src/app/vault/individual-vault/vault-next.component.html"),
        encoding="utf-8",
    ).read()
    layout = open(
        os.path.join(CLIENTS, "apps/web/src/app/layouts/user-layout.component.html"),
        encoding="utf-8",
    ).read()
    routing = open(
        os.path.join(CLIENTS, "apps/web/src/app/oss-routing.module.ts"),
        encoding="utf-8",
    ).read()
    assert "app-vault-onboarding" not in vault
    assert "app-vault-onboarding" not in nxt
    assert "app-vault-filter" in vault
    assert "app-vault-items" in vault
    assert "md:tw-flex-row" in vault
    assert layout.count('data-testid="nav-downloads"') == 2
    assert 'route="downloads"' in layout
    assert 'path: "downloads"' in routing
    assert 'path: "register"' in routing
    assert "SetupExtensionComponent" in routing
    marketing = open(os.path.join(ROOT, "apps/web-marketing/downloads.html"), encoding="utf-8").read()
    assert "docs/BROWSER-EXTENSIONS.md" in marketing
    assert "nngceckbapebfimnlniiiahkandclblb" not in marketing
    assert "coming soon" in marketing.lower()


def fixture(route_rows):
    os.makedirs(OUT, exist_ok=True)
    mark = os.path.join(CLIENTS, "apps/web/src/images/komboe-mark.svg")
    shutil.copy(mark, os.path.join(OUT, "komboe-mark.svg"))
    item = open(os.path.join(CLIENTS, "libs/assets/src/svg/svgs/item-types.ts"), encoding="utf-8").read()
    svg = item.split("<svg", 1)[1]
    svg = "<svg" + svg.split("</svg>", 1)[0] + "</svg>"
    open(os.path.join(OUT, "empty.svg"), "w", encoding="utf-8").write(svg)
    route_html = "\n".join(
        f"<li><code>{p or '/'}</code> <span>{src}</span></li>" for src, p in route_rows[:80]
    )
    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Komboe signed-in vault fixture</title>
<style>
  body {{ margin:0; font-family: system-ui, sans-serif; color:#172033; background:#f4f6f8; }}
  .app {{ display:flex; min-height:100vh; }}
  aside {{ width:220px; background:#4a28c9; color:#fff; padding:18px 14px; }}
  aside .brand {{ display:flex; align-items:center; gap:8px; font-weight:700; font-size:20px; }}
  aside nav a {{ display:block; color:#fff; text-decoration:none; padding:8px; border-radius:8px; }}
  aside nav a.on {{ background:rgba(255,255,255,.16); }}
  main {{ flex:1; padding:24px 28px; }}
  .card {{ background:#fff; border:1px solid #e4e7ec; border-radius:12px; padding:16px 18px; margin-bottom:16px; }}
  .row {{ display:flex; gap:12px; align-items:center; }}
  .empty {{ text-align:center; padding:28px 12px 8px; }}
  h1 {{ font-size:22px; margin:0 0 16px; }}
  table {{ width:100%; border-collapse:collapse; }}
  th {{ text-align:left; color:#667085; font-weight:600; border-bottom:1px solid #eaecf0; padding:8px; }}
  a {{ color:#3b2f8a; }}
  .routes {{ font-size:12px; columns:2; }}
  .routes li {{ break-inside:avoid; margin:2px 0; }}
  code {{ background:#f2f4f7; padding:0 4px; }}
</style></head>
<body>
<div class="app">
  <aside>
    <div class="brand"><img src="komboe-mark.svg" width="28" height="28" alt=""> Komboe</div>
    <nav>
      <a class="on" href="#/vault">Vaults</a>
      <a href="#/sends">Send</a>
      <a href="#/tools/generator">Tools</a>
      <a href="#/reports">Reports</a>
      <a href="#/settings">Settings</a>
    </nav>
  </aside>
  <main>
    <h1>All vaults</h1>
    <section class="card">
      <div class="row">
        <img src="komboe-mark.svg" width="32" height="32" alt="">
        <div><strong>Get started with your vault</strong><br>Complete these steps to secure your personal data and get the most out of Komboe</div>
      </div>
    </section>
    <section class="card empty">
      <img src="empty.svg" width="72" height="72" alt="Komboe">
      <h2>No items in the vault</h2>
      <p>The vault protects more than just your passwords. Store secure logins, IDs, cards and notes securely here.</p>
    </section>
    <section class="card">
      <p>Terms and privacy use the owned drafts, not bitwarden.com.</p>
      <p>
        <a href="https://github.com/GoDeskio/Komboe/blob/main/apps/web-marketing/terms.html">Terms of Service</a>
        ·
        <a href="https://github.com/GoDeskio/Komboe/blob/main/apps/web-marketing/privacy.html">Privacy Policy</a>
        ·
        <a href="https://github.com/GoDeskio/Komboe/blob/main/docs/BROWSER-EXTENSIONS.md">Install extension</a>
      </p>
    </section>
    <section class="card">
      <strong>Route inventory (web routing modules)</strong>
      <ul class="routes">{route_html}</ul>
    </section>
  </main>
</div>
</body></html>
"""
    def page(show_panel):
        panel = ""
        if show_panel:
            panel = """
    <section class="card">
      <div class="row">
        <img src="komboe-mark.svg" width="32" height="32" alt="">
        <div><strong>Get started with your vault</strong><br>Create your account · Import your passwords · Install the browser extension</div>
      </div>
    </section>"""
        return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Komboe vault</title>
<style>
  body {{ margin:0; font-family: system-ui, sans-serif; color:#172033; background:#f6f7f9; }}
  .app {{ display:flex; min-height:100vh; }}
  aside {{ width:200px; background:#4a28c9; color:#fff; padding:16px 12px; flex:none; }}
  aside .brand {{ display:flex; align-items:center; gap:8px; font-weight:700; font-size:18px; margin-bottom:16px; }}
  aside a {{ display:block; color:#fff; text-decoration:none; padding:8px; border-radius:8px; }}
  aside a.on {{ background:rgba(255,255,255,.18); }}
  main {{ flex:1; padding:20px; min-width:0; }}
  .card {{ background:#fff; border:1px solid #e6e8ee; border-radius:12px; padding:16px; margin-bottom:16px; }}
  .row {{ display:flex; gap:12px; align-items:center; }}
  .vault {{ display:flex; gap:16px; }}
  .filters {{ width:220px; flex:none; }}
  .items {{ flex:1; text-align:center; }}
  h1 {{ margin:0 0 16px; font-size:22px; }}
  @media (max-width: 700px) {{
    aside {{ width:72px; }}
    aside .label {{ display:none; }}
    .vault {{ flex-direction:column; }}
    .filters, .items {{ width:100%; }}
  }}
</style></head>
<body><div class="app">
  <aside>
    <div class="brand"><img src="komboe-mark.svg" width="28" height="28" alt=""><span class="label">Komboe</span></div>
    <a class="on" href="#/vault"><span class="label">Vaults</span></a>
    <a href="#/sends"><span class="label">Send</span></a>
    <a href="#/tools"><span class="label">Tools</span></a>
    <a href="#/downloads" data-testid="nav-downloads"><span class="label">Downloads</span></a>
    <a href="#/reports"><span class="label">Reports</span></a>
    <a href="#/settings"><span class="label">Settings</span></a>
  </aside>
  <main>
    <h1>All vaults</h1>
    {panel}
    <section class="card vault">
      <div class="filters"><strong>Filters</strong><p>All vaults<br>My vault<br>All items</p></div>
      <div class="items">
        <img src="empty.svg" width="72" height="72" alt="Komboe">
        <h2>No items in the vault</h2>
        <p>The vault protects more than just your passwords.</p>
      </div>
    </section>
  </main>
</div></body></html>"""

    chrome = shutil.which("google-chrome") or shutil.which("chromium") or shutil.which("chromium-browser")
    assert chrome, "chrome is required to screenshot the signed-in fixture"
    shots = []
    for name, show_panel, size in (
        ("before-desktop", True, "1400,900"),
        ("before-mobile", True, "390,844"),
        ("after-desktop", False, "1400,900"),
        ("after-mobile", False, "390,844"),
    ):
        html_path = os.path.join(OUT, f"{name}.html")
        shot = os.path.join(OUT, f"{name}.png")
        open(html_path, "w", encoding="utf-8").write(page(show_panel))
        proc = subprocess.Popen(
            [
                chrome,
                "--headless=new",
                "--disable-gpu",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--hide-scrollbars",
                f"--user-data-dir=/tmp/komboe-chrome-{name}",
                f"--window-size={size}",
                f"--screenshot={shot}",
                "file://" + html_path,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
        assert os.path.isfile(shot) and os.path.getsize(shot) > 8_000, shot
        shots.append(shot)
    return shots


def main():
    hits, shields = scan()
    assert not shields, "Bitwarden shield still in a template:\n" + "\n".join(shields)
    assert not hits, "commercial branding links remain:\n" + "\n".join(hits[:30])
    fav = favicons()
    assert not fav, "favicon bytes do not match the Komboe kit:\n" + "\n".join(fav)
    empty_state()
    import_formats_kept()
    en = open(os.path.join(CLIENTS, "apps/web/src/locales/en/messages.json"), encoding="utf-8").read()
    assert "emails bitwarden sends" not in en
    assert "have bitwarden send" not in en
    found, missing = routes()
    assert not missing, f"expected routes missing from inventory: {missing}"
    # Signed-in surfaces must be in the inventory, not only login.
    blob = " ".join(p for _, p in found)
    for token in ("vault", "settings", "tools", "reports"):
        assert token in blob, token
    dashboard_contract()
    bad_live = live_urls()
    assert not bad_live, "owned destinations did not respond:\n" + "\n".join(bad_live)
    shots = fixture(found)
    print(f"BRANDING SURFACE PASS routes={len(found)} screenshots={shots}")
    print("ROUTE INVENTORY")
    for src, path in found:
        print(f"  {path or '/'}  ({src})")


if __name__ == "__main__":
    main()
