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
        page.wait_for_selector("img.new-logo-themed")
        logo = page.evaluate("""() => getComputedStyle(document.querySelector('img.new-logo-themed')).content""")
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
        assert page.evaluate("() => document.documentElement.classList.contains('theme_light')")
        page.get_by_test_id("komboe-theme").click()
        assert page.evaluate("() => document.documentElement.classList.contains('theme_dark')")
        page.get_by_test_id("komboe-theme").click()
        assert page.evaluate("() => document.documentElement.classList.contains('theme_light')")
        browser.close()
    print("DASHBOARD WEB PASS")

if __name__ == "__main__":
    main()
