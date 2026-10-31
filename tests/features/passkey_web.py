#!/usr/bin/env python3
"""#50 Log in with a passkey: register in the real web vault (CDP virtual authenticator
with PRF), sign out, sign back in with the passkey only, and land in an unlocked vault."""
import importlib.util, json, os, sys

spec = importlib.util.spec_from_file_location("ft", os.path.join(os.path.dirname(__file__), "run.py"))
ft = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ft)

# WebAuthn RP id is the configured domain host, so the browser must use it.
WEB = os.environ.get("KOMBOE_PASSKEY_WEB", "https://localhost:8443")
SECRET = "passkey50-item-secret"


def main():
    from playwright.sync_api import sync_playwright
    user = ft.User()
    c = user.api("POST", "/api/ciphers", user.cipher({"login": {"username": user.e("ada"), "password": user.e(SECRET), "uris": []}}))
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        ctx = browser.new_context(ignore_https_errors=True, viewport={"width": 1400, "height": 900})
        page = ctx.new_page()
        page.set_default_timeout(25000)
        cdp = ctx.new_cdp_session(page)
        cdp.send("WebAuthn.enable")
        auth = cdp.send("WebAuthn.addVirtualAuthenticator", {"options": {
            "protocol": "ctap2", "ctap2Version": "ctap2_1", "transport": "internal", "hasResidentKey": True,
            "hasUserVerification": True, "isUserVerified": True, "hasPrf": True,
            "automaticPresenceSimulation": True}})["authenticatorId"]
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
        page.wait_for_timeout(1500)
        skip = page.locator(".cdk-overlay-container").get_by_role("button", name="Skip")
        if skip.count():
            skip.click()
            page.wait_for_timeout(300)
        page.goto(WEB + "/#/settings/security/password")
        try:
            page.get_by_role("button", name="Turn on Log in with passkey").click()
        except Exception:
            page.screenshot(path="/tmp/pk50.png"); print(page.url); raise
        dlg = page.locator(".cdk-overlay-container")
        dlg.locator("app-user-verification input[type=password]").fill(user.pw)
        dlg.get_by_role("button", name="Continue").click()
        try:
            dlg.locator("input[formcontrolname=name]").wait_for(timeout=40000)
        except Exception:
            page.screenshot(path="/tmp/pk50.png"); raise
        dlg.locator("input[formcontrolname=name]").fill("Komboe test key")
        box = dlg.locator("input[formcontrolname=useForEncryption]")
        if not box.is_checked():
            box.check()
        dlg.get_by_role("button", name="Turn on").click()
        page.get_by_text("Komboe test key").first.wait_for(timeout=40000)
        page.get_by_text("Used for encryption").first.wait_for()
        creds = cdp.send("WebAuthn.getCredentials", {"authenticatorId": auth})["credentials"]
        assert len(creds) == 1 and creds[0]["isResidentCredential"], creds

        # Log out through the account menu (clears tokens and keys), then sign in with only the passkey.
        page.locator("bit-layout header button, app-header button").filter(has=page.locator("bit-avatar")).first.click()
        page.get_by_role("menuitem", name="Log out").click()
        page.wait_for_function("() => location.hash.includes('login')", timeout=20000)
        page.wait_for_timeout(2500)
        try:
            page.get_by_test_id("login-with-passkey-button").click()
        except Exception:
            page.screenshot(path="/tmp/pk50.png"); print(page.url); raise
        try:
            page.wait_for_function("() => /vault|setup-extension/.test(location.hash)", timeout=60000)
        except Exception:
            page.screenshot(path="/tmp/pk50.png"); print(page.url); raise
        if "setup-extension" in page.url:
            page.get_by_role("button", name="Add it later").click()
            page.wait_for_timeout(800)
            page.get_by_role("link", name="Skip to web app").click()
            page.wait_for_function("() => location.hash.includes('vault')", timeout=20000)
        assert "lock" not in page.url, page.url
        page.wait_for_timeout(1500)
        assert page.locator("#masterPassword").count() == 0, "passkey PRF should unlock without the master password"
        try:
            page.locator(f"text={user.d(c['name'])} >> visible=true").first.wait_for(timeout=30000)
        except Exception:
            page.screenshot(path="/tmp/pk50.png"); print(page.url); raise
        browser.close()

    # Server side: list shows PRF enabled, stored material is client ciphertext only.
    lst = user.api("GET", "/api/webauthn")["data"]
    assert len(lst) == 1 and lst[0]["prfStatus"] == 0 and lst[0]["name"] == "Komboe test key", lst
    assert lst[0]["encryptedUserKey"].split(".")[0] in ("2", "4", "7"), lst[0]["encryptedUserKey"][:4]
    import sqlite3
    db = sqlite3.connect(os.environ["KOMBOE_DB"])
    rows = db.execute("select encrypted_user_key, encrypted_private_key, credential from komboe_login_passkeys where user_uuid=?", (user.id,)).fetchall()
    assert len(rows) == 1 and all(r and "." in r for r in rows[0][:2]), rows
    assert "prf" not in rows[0][2].lower() or "results" not in rows[0][2], "PRF output must never be stored"
    # Adding a login passkey must not turn on two-step login.
    assert not user.api("GET", "/api/two-factor")["data"], "passkey must not count as 2FA"
    # A bad assertion is refused.
    opts = ft.http("GET", "/identity/accounts/webauthn/assertion-options")
    try:
        ft.http("POST", "/identity/connect/token", form={"grant_type": "webauthn", "token": opts["token"], "scope": "api offline_access",
                "client_id": "web", "deviceResponse": json.dumps({"id": "AAAA", "rawId": "AAAA", "type": "public-key", "extensions": {},
                "response": {"authenticatorData": "AAAA", "signature": "AAAA", "clientDataJson": "AAAA", "userHandle": "AAAA"}}),
                "deviceType": "9", "deviceIdentifier": "11111111-1111-1111-1111-111111111111", "deviceName": "x"})
        raise SystemExit("forged passkey assertion was accepted")
    except ft.HTTPErr as e:
        assert e.code == 400 and "Passkey sign-in failed" in e.body, e.body
    try:
        ft.http("POST", "/identity/connect/token", form={"grant_type": "webauthn", "token": opts["token"], "scope": "api offline_access",
                "client_id": "web", "deviceResponse": "{}", "deviceType": "9",
                "deviceIdentifier": "11111111-1111-1111-1111-111111111111", "deviceName": "x"})
        raise SystemExit("used challenge token was accepted twice")
    except ft.HTTPErr as e:
        assert e.code == 400, e.body
    print("PASSKEY WEB PASS")


if __name__ == "__main__":
    main()
