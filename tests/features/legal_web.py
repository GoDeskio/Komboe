#!/usr/bin/env python3
"""Legal notice: exact attribution text + View license / Source code links in the web login footer and the web
About page, and in the installed extension and desktop builds; license texts bundled with every client."""
import glob, os, re, ssl, sys, urllib.request
sys.path.insert(0, os.path.dirname(__file__))
from branding_web import NOTICE  # single copy of the approved text

WEB = os.environ.get("KOMBOE_WEB") or os.environ.get("KOMBOE_URL") or "https://127.0.0.1:8443"
WEB_VAULT = os.environ.get("KOMBOE_WEB_VAULT", "/workspace/run/web-vault")
EXT = os.environ.get("KOMBOE_EXT_DIR", "/workspace/run/ext")
DESK = os.environ.get("KOMBOE_DESKTOP", "/workspace/run/desk/squashfs-root")
FILES = ["LICENSE.txt", "LICENSE_GPL.txt", "THIRD-PARTY-NOTICES.md"]
LINK = re.compile(r"^https://github\.com/GoDeskio/Komboe/(blob/[\w.\-/]+/LICENSE|tree/[\w.\-/]+)$")


def check_links(page):
    lic = page.get_by_test_id("komboe-license-link").first.get_attribute("href")
    src = page.get_by_test_id("komboe-source-link").first.get_attribute("href")
    assert LINK.match(lic) and lic.endswith("/LICENSE"), lic
    assert LINK.match(src) and "/tree/" in src, src
    assert page.get_by_test_id("komboe-license-link").first.inner_text().strip() == "View license"
    assert page.get_by_test_id("komboe-source-link").first.inner_text().strip() == "Source code"
    return src


def bundled(root, label):
    for f in FILES:
        p = os.path.join(root, f)
        assert os.path.isfile(p) and os.path.getsize(p) > 200, f"{label} missing {f}"


def notice_in(root):
    for f in glob.glob(root + "/**/*.js", recursive=True):
        if NOTICE.encode() in open(f, "rb").read():
            return f
    return None


def main():
    ssl._create_default_https_context = ssl._create_unverified_context
    # License texts are bundled and served.
    bundled(WEB_VAULT, "web vault")
    for f in FILES:
        body = urllib.request.urlopen(f"{WEB}/{f}").read()
        assert len(body) > 200, f
    assert b"GNU AFFERO GENERAL PUBLIC LICENSE" in open(os.path.join(WEB_VAULT, "LICENSE.txt"), "rb").read()
    assert b"GNU GENERAL PUBLIC LICENSE" in open(os.path.join(WEB_VAULT, "LICENSE_GPL.txt"), "rb").read()
    bundled(EXT, "extension")
    assert notice_in(EXT), "extension bundle has no legal notice"
    # Desktop: notice compiled into the shipped app.asar (main-process About dialog + renderer).
    asar = os.path.join(DESK, "resources", "app.asar")
    data = open(asar, "rb").read()
    assert data.count(NOTICE.encode()) >= 1, "desktop app.asar has no legal notice"
    for f in FILES:
        assert f.encode() in data, f"desktop app.asar missing {f}"
    assert b"View license" in data and b"Source code" in data

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        page = browser.new_page(ignore_https_errors=True, viewport={"width": 1400, "height": 900})
        page.set_default_timeout(25000)
        page.goto(WEB + "/#/login", wait_until="domcontentloaded")
        page.wait_for_selector("#email")
        page.wait_for_selector("[data-testid=komboe-legal-notice]")
        assert page.get_by_test_id("komboe-legal-notice").first.inner_text().strip() == NOTICE
        src = check_links(page)
        page.goto(WEB + "/#/about", wait_until="domcontentloaded")
        page.wait_for_selector("[data-testid=about-page]")
        about = page.get_by_test_id("about-page")
        assert NOTICE in about.inner_text(), about.inner_text()
        assert re.search(r"Version \d", page.get_by_test_id("about-version").inner_text())
        assert check_links(about) == src
        browser.close()
    print("LEGAL WEB PASS", src)


if __name__ == "__main__":
    main()
