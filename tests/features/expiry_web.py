#!/usr/bin/env python3
"""A login shows the password-expired banner after the personal expiry setting is 0 days."""
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
        page.fill("[data-testid=password-expiry-days]", "0")
        page.click("[data-testid=password-expiry-save]")
        page.get_by_test_id("password-expiry-saved").wait_for()
        page.locator("#newItemDropdown").click()
        page.get_by_role("menuitem", name="Login", exact=True).click()
        page.fill("input[formcontrolname=name]", "Old login")
        page.fill("input[formcontrolname=password]", "still-secret-value")
        page.get_by_role("button", name="Save", exact=True).click()
        page.keyboard.press("Escape")
        page.get_by_text("Old login", exact=True).first.click()
        page.get_by_test_id("password-expired").wait_for()
        page.keyboard.press("Escape")
        browser.close()
    raw = open(os.environ["KOMBOE_DB"], "rb").read()
    if b"still-secret-value" in raw:
        raise SystemExit("login password stored in plaintext")
    print("EXPIRY WEB PASS")

if __name__ == "__main__":
    main()
