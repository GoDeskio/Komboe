#!/usr/bin/env python3
"""Create a tag in the real Komboe web vault and attach it to a login."""
import importlib.util, os, sys, time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
spec = importlib.util.spec_from_file_location("ft", os.path.join(os.path.dirname(__file__), "run.py"))
ft = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ft)

WEB = os.environ.get("KOMBOE_WEB") or os.environ.get("KOMBOE_URL") or "https://127.0.0.1:8443"

def main():
    import ssl
    ssl._create_default_https_context = ssl._create_unverified_context
    from playwright.sync_api import sync_playwright
    u = ft.User()
    item = "Tagged lighthouse"
    tag = "Coast"
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        page = browser.new_page(ignore_https_errors=True, viewport={"width": 1400, "height": 900})
        page.set_default_timeout(25000)
        page.goto(WEB + "/#/login", wait_until="domcontentloaded")
        page.fill("#email", u.email)
        cont = page.get_by_role("button", name="Continue")
        if cont.count():
            cont.click()
        page.fill("#masterPassword", u.pw)
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
        page.locator("#newItemDropdown").click()
        page.get_by_role("menuitem", name="Login").click()
        page.fill("input[formcontrolname=name]", item)
        page.fill("input[formcontrolname=username]", "ada")
        page.fill("input[formcontrolname=password]", "tag-secret-value")
        page.get_by_role("button", name="Save", exact=True).click()
        page.keyboard.press("Escape")
        page.get_by_text(item, exact=True).first.wait_for()
        page.wait_for_selector("[data-testid=komboe-tags]")
        page.fill("[data-testid=tag-name]", tag)
        page.click("[data-testid=tag-create]")
        page.get_by_role("button", name=tag, exact=True).wait_for()
        page.select_option("[data-testid=tag-item]", label=item)
        page.click("[data-testid=tag]")
        page.click("[data-testid=tag-assign]")
        page.get_by_test_id("tagged-item").filter(has_text=item).wait_for()
        browser.close()
    raw = open(os.environ["KOMBOE_DB"], "rb").read()
    if tag.encode() in raw or b"tag-secret-value" in raw:
        raise SystemExit("plaintext tag or item secret stored in the server database")
    print("TAGS WEB PASS")

if __name__ == "__main__":
    main()
