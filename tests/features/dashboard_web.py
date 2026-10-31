#!/usr/bin/env python3
"""The real web vault uses Sora, the locked logo, and light/dark."""
import importlib.util, os, sys
spec = importlib.util.spec_from_file_location("ft", os.path.join(os.path.dirname(__file__), "run.py"))
ft = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ft)
WEB = os.environ.get("KOMBOE_WEB") or os.environ.get("KOMBOE_URL") or "https://127.0.0.1:8443"

def main():
    import ssl
    ssl._create_default_https_context = ssl._create_unverified_context
    from playwright.sync_api import sync_playwright
    user = ft.User()
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        page = browser.new_page(ignore_https_errors=True, viewport={"width": 1400, "height": 900})
        page.set_default_timeout(25000)
        page.goto(WEB + "/#/login", wait_until="domcontentloaded")
        # The themed logo lives on the pre-boot screen, which Angular removes; probe the same CSS rule deterministically.
        page.wait_for_selector("#email")
        logo = page.evaluate("""() => { const i = document.createElement('img'); i.className = 'new-logo-themed';
            document.body.appendChild(i); const c = getComputedStyle(i).content; i.remove(); return c; }""")
        assert "logo" in logo, logo
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
        dismiss = page.get_by_role("button", name="Dismiss this checklist")
        if dismiss.count():
            dismiss.click()
        overlay = page.locator(".cdk-overlay-container")
        skip_tour = overlay.get_by_role("button", name="Skip")
        if skip_tour.count():
            skip_tour.click()
            page.wait_for_timeout(300)
        font = page.evaluate("() => getComputedStyle(document.body).fontFamily")
        assert "Sora" in font, font
        loaded = page.evaluate("async () => { await document.fonts.ready; await document.fonts.load('16px Sora'); return document.fonts.check('16px Sora') && [...document.fonts].some(f => f.family.replace(/\"/g, '') === 'Sora' && f.status === 'loaded'); }")
        assert loaded, "Sora font face did not load"
        assert page.evaluate("() => document.documentElement.classList.contains('theme_light')")
        page.get_by_test_id("komboe-theme").click()
        assert page.evaluate("() => document.documentElement.classList.contains('theme_dark')")
        page.wait_for_timeout(1000)
        page.reload(wait_until="domcontentloaded")
        # A reload locks the web vault; the theme is global state, so it must already apply on the lock screen.
        page.wait_for_function("() => location.hash.includes('lock') || document.querySelector('[data-testid=komboe-theme]')", timeout=40000)
        page.wait_for_timeout(1500)
        assert page.evaluate("() => document.documentElement.classList.contains('theme_dark')"), "dark theme did not persist across reload"
        if "lock" in page.url:
            page.get_by_label("Master password").fill(user.pw)
            page.get_by_role("button", name="Unlock", exact=True).click()
        page.get_by_test_id("komboe-theme").wait_for(timeout=40000)
        assert page.evaluate("() => document.documentElement.classList.contains('theme_dark')"), "dark theme did not persist across reload"
        page.get_by_test_id("komboe-theme").click()
        assert page.evaluate("() => document.documentElement.classList.contains('theme_light')")
        browser.close()
    print("DASHBOARD WEB PASS")

if __name__ == "__main__":
    main()
