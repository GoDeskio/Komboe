#!/usr/bin/env python3
"""No leftover Bitwarden/Vaultwarden branding in the real web vault, server config, or built client bundles."""
import glob, importlib.util, json, os, re, ssl, sys, urllib.request
spec = importlib.util.spec_from_file_location("ft", os.path.join(os.path.dirname(__file__), "run.py"))
ft = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ft)
WEB = os.environ.get("KOMBOE_WEB") or os.environ.get("KOMBOE_URL") or "https://127.0.0.1:8443"
BAD = re.compile(r"Bitwarden|Vaultwarden", re.I)
# The legal attribution notice (docs/LICENSE-AUDIT.md) must name upstream projects; it is the only allowed mention.
NOTICE = ("Komboe © 2026 GODESK IO LLC. Komboe is based on Vaultwarden (© Vaultwarden contributors, AGPL-3.0) "
          "and Bitwarden clients (© Bitwarden Inc., GPL-3.0). Komboe is not affiliated with or endorsed by "
          "Bitwarden Inc. or the Vaultwarden project. This program comes with ABSOLUTELY NO WARRANTY. It is free "
          "software: you may redistribute and modify it under the GNU GPL v3 / AGPL v3.")
ALLOWED_BYTES = [b"Bitwarden Inc., GPL-3.0", b"endorsed by Bitwarden Inc. or the Vaultwarden"]

def strip_notice(data):
    # THIRD-PARTY-NOTICES.md is bundled (inside app.asar too) and must credit upstream copyright holders.
    data = re.sub(rb"# Third-party notices.*?used here only to describe origin\.", b"", data, flags=re.S)
    for a in ALLOWED_BYTES:
        data = data.replace(a, b"")
    return data
ROUTES = ["vault", "sends", "tools/generator", "tools/import", "tools/export", "reports", "settings/account",
          "settings/security/two-factor", "settings/preferences", "settings/emergency-access", "settings/subscription"]

def visible(page):
    return page.evaluate("() => document.title + '\\n' + document.body.innerText + '\\n' + [...document.querySelectorAll('img[alt],[title],[aria-label]')].map(e => (e.alt||'') + ' ' + (e.title||'') + ' ' + (e.getAttribute('aria-label')||'')).join('\\n')")

def bundles():
    """Built bundles must not carry the upstream copyright line / product name in UI strings."""
    # Scan what is installed: web vault, unpacked extension, and the desktop app.asar actually shipped.
    roots = [os.environ.get("KOMBOE_WEB_VAULT", "/workspace/run/web-vault"), os.environ.get("KOMBOE_EXT_DIR", "/workspace/run/ext")]
    pat = re.compile(rb"Bitwarden Inc\.|Bitwarden phishing blocker|Bitwarden inline menu|<title>Bitwarden|Unlock Bitwarden|Bitwarden desktop app|issuer=Bitwarden")
    hits = []
    for r in roots:
        for f in glob.glob(r + "/**/*", recursive=True):
            if os.path.isfile(f) and f.endswith((".js", ".html", ".json")) and os.path.getsize(f) < 60_000_000:
                for m in pat.finditer(strip_notice(open(f, "rb").read())):
                    hits.append(f"{f}: {m.group(0).decode()}")
    desk = os.environ.get("KOMBOE_DESKTOP", "/workspace/run/desk/squashfs-root")
    asar = os.path.join(desk, "resources", "app.asar")
    assert os.path.isfile(asar), asar
    for m in pat.finditer(strip_notice(open(asar, "rb").read())):
        hits.append(f"{asar}: {m.group(0).decode()}")
    return hits

def main():
    ssl._create_default_https_context = ssl._create_unverified_context
    cfg = json.load(urllib.request.urlopen(WEB + "/api/config"))
    assert cfg["server"]["name"] == "Komboe", cfg["server"]
    assert cfg["server"]["url"] == "https://github.com/GoDeskio/Komboe", cfg["server"]
    hits = bundles()
    assert not hits, "\n".join(hits[:20])
    from playwright.sync_api import sync_playwright
    user = ft.User()
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        page = browser.new_page(ignore_https_errors=True, viewport={"width": 1400, "height": 900})
        page.set_default_timeout(25000)
        page.goto(WEB + "/#/login", wait_until="domcontentloaded")
        page.wait_for_selector("#email")
        page.wait_for_timeout(800)
        text = visible(page)
        assert NOTICE in text, text[-600:]
        text = text.replace(NOTICE, "")
        assert "Komboe" in text, text[-300:]
        assert not BAD.search(text), BAD.findall(text)
        page.fill("#email", user.email)
        cont = page.get_by_role("button", name="Continue")
        if cont.count():
            cont.click()
        page.fill("#masterPassword", user.pw)
        page.get_by_role("button", name="Log in", exact=True).click()
        page.wait_for_url("**/setup-extension**", timeout=40000)
        page.get_by_role("button", name="Add it later").click()
        page.wait_for_timeout(800)
        page.get_by_role("link", name="Skip to web app").click()
        page.wait_for_function("() => location.hash.includes('vault')", timeout=20000)
        bad = {}
        for r in ROUTES:
            page.evaluate(f"() => location.hash = '#/{r}'")
            page.wait_for_timeout(2500)
            found = sorted(set(m.group(0) for m in BAD.finditer(visible(page))))
            ctx = [l for l in visible(page).splitlines() if BAD.search(l)]
            if found:
                bad[r] = ctx[:5]
        assert not bad, json.dumps(bad, indent=1)
        browser.close()
    print("BRANDING WEB PASS")

if __name__ == "__main__":
    main()
