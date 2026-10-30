#!/usr/bin/env python3
"""Create Wi-Fi, passport, license, and bank items in the real Komboe web vault."""
import importlib.util, os, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
spec = importlib.util.spec_from_file_location("ft", os.path.join(os.path.dirname(__file__), "run.py"))
ft = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ft)

WEB = os.environ.get("KOMBOE_WEB") or os.environ.get("KOMBOE_URL") or "https://127.0.0.1:8443"

SECRETS = {
    "Harbor Bank": "bank-acct-88421",
    "Ada Passport": "P4488123",
    "Ada License": "DL998877",
    "Cafe Wi-Fi": "wifi-secret-value",
}


def login(page, user):
    page.goto(WEB + "/#/login", wait_until="domcontentloaded")
    page.fill("#email", user.email)
    cont = page.get_by_role("button", name="Continue")
    if cont.count():
        cont.click()
    page.fill("#masterPassword", user.pw)
    field = page.locator("bit-form-field").filter(has=page.locator("#masterPassword"))
    toggle = field.locator("button").last
    assert toggle.count() == 1, "master password is missing a show/hide toggle"
    toggle.click()
    assert page.locator("#masterPassword").get_attribute("type") == "text"
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


def open_menu(page, label):
    page.locator("#newItemDropdown").click()
    page.get_by_role("menuitem", name=label, exact=True).click()


def save(page, name):
    page.get_by_role("button", name="Save", exact=True).click()
    page.keyboard.press("Escape")
    page.get_by_text(name, exact=True).first.wait_for()


def reveal(page, field_id, toggle_id, secret):
    page.get_by_test_id(field_id).wait_for()
    field = page.get_by_test_id(field_id)
    assert field.get_attribute("type") == "password", field_id
    page.get_by_test_id(toggle_id).click()
    page.wait_for_timeout(200)
    assert field.input_value() == secret, (field_id, field.input_value())
    assert field.get_attribute("type") == "text", field_id


def main():
    import ssl
    ssl._create_default_https_context = ssl._create_unverified_context
    from playwright.sync_api import sync_playwright

    user = ft.User()
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        page = browser.new_page(ignore_https_errors=True, viewport={"width": 1400, "height": 900})
        page.set_default_timeout(25000)
        login(page, user)

        # Login password eye is present on the master password field before submit; checked above by reaching the vault.
        open_menu(page, "Bank account")
        page.fill("input[formcontrolname=name]", "Harbor Bank")
        page.fill("[data-testid=account-number]", SECRETS["Harbor Bank"])
        page.fill("[data-testid=pin]", "4491")
        reveal_form = page.get_by_test_id("toggle-account-number-visibility")
        reveal_form.click()
        assert page.get_by_test_id("account-number").get_attribute("type") == "text"
        page.get_by_test_id("toggle-pin-visibility").click()
        assert page.get_by_test_id("pin").get_attribute("type") == "text"
        save(page, "Harbor Bank")

        open_menu(page, "Passport")
        page.fill("input[formcontrolname=name]", "Ada Passport")
        page.fill("[data-testid=passport-number]", SECRETS["Ada Passport"])
        page.get_by_test_id("toggle-passport-number-form").click()
        assert page.get_by_test_id("passport-number").get_attribute("type") == "text"
        save(page, "Ada Passport")

        open_menu(page, "License")
        page.fill("input[formcontrolname=name]", "Ada License")
        page.fill("#licenseNumber", SECRETS["Ada License"])
        page.get_by_test_id("toggle-license-number-form").click()
        assert page.locator("#licenseNumber").get_attribute("type") == "text"
        save(page, "Ada License")

        open_menu(page, "Wi-Fi")
        page.fill("input[formcontrolname=name]", "Cafe Wi-Fi")
        page.fill("[data-testid=wifi-ssid]", "CafeNet")
        page.fill("[data-testid=wifi-password]", SECRETS["Cafe Wi-Fi"])
        page.get_by_test_id("toggle-wifi-password").click()
        assert page.get_by_test_id("wifi-password").get_attribute("type") == "text"
        assert page.get_by_test_id("wifi-password").input_value() == SECRETS["Cafe Wi-Fi"]
        save(page, "Cafe Wi-Fi")

        page.get_by_text("Harbor Bank", exact=True).first.click()
        reveal(page, "account-number", "toggle-account-number", SECRETS["Harbor Bank"])
        page.keyboard.press("Escape")

        page.get_by_text("Ada Passport", exact=True).first.click()
        reveal(page, "passport-number", "toggle-passport-number", SECRETS["Ada Passport"])
        page.keyboard.press("Escape")

        page.get_by_text("Ada License", exact=True).first.click()
        reveal(page, "license-number", "toggle-license-number", SECRETS["Ada License"])
        page.keyboard.press("Escape")

        page.get_by_text("Cafe Wi-Fi", exact=True).first.click()
        reveal(page, "wifi-password", "toggle-wifi-password", SECRETS["Cafe Wi-Fi"])
        ssid = page.get_by_test_id("wifi-ssid")
        assert ssid.input_value() == "CafeNet"
        page.keyboard.press("Escape")
        browser.close()

    raw = open(os.environ["KOMBOE_DB"], "rb").read()
    for secret in list(SECRETS.values()) + ["CafeNet", "__komboe"]:
        blob = secret if isinstance(secret, bytes) else secret.encode()
        if blob in raw:
            raise SystemExit(f"plaintext {blob!r} stored in the server database")
    print("TEMPLATES WEB PASS")


if __name__ == "__main__":
    main()
