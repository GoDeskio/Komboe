#!/usr/bin/env python3
"""Web vault: SSO, trust this browser, then SSO again with no master password."""
import importlib.util
import os
import shutil
import subprocess
import time

spec = importlib.util.spec_from_file_location("sso_dex", os.path.join(os.path.dirname(__file__), "sso_dex.py"))
sso_dex = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sso_dex)

BIN = os.environ.get("KOMBOE_BIN", "/workspace/server/upstream/target/release/vaultwarden")
DEX = os.environ.get("KOMBOE_DEX_BIN", "/tmp/dex-bin/dex")
WEB = "https://127.0.0.1:18443"
DEX_ISSUER = "http://127.0.0.1:5560/dex"
EMAIL = sso_dex.EMAIL
PASSWORD = sso_dex.PASSWORD


def dex_login(page):
    page.locator("input[name=login]").wait_for()
    page.fill("input[name=login]", EMAIL)
    page.fill("input[name=password]", PASSWORD)
    page.locator("button[type=submit], #submit-login").first.click()


def sso(page):
    page.goto(WEB + "/#/login", wait_until="domcontentloaded")
    page.fill("#email", EMAIL)
    page.get_by_test_id("login-sso-button").click()
    page.wait_for_function(
        "() => !!document.querySelector('input[name=login]') || !!document.querySelector('input[formcontrolname=identifier]')",
        timeout=20000,
    )
    ident = page.locator("input[formcontrolname=identifier]")
    if ident.count():
        ident.fill("komboe")
        page.get_by_role("button", name="Continue").click()
    dex_login(page)


def dismiss(page):
    overlay = page.locator(".cdk-overlay-container")
    for name in ("Skip", "Add it later"):
        button = page.get_by_role("button", name=name)
        if button.count():
            button.first.click()
            page.wait_for_timeout(300)
    skip = overlay.get_by_role("button", name="Skip")
    if skip.count():
        skip.first.click()


def main():
    folder = "/tmp/komboe-trusted-web"
    if os.path.isdir(folder):
        shutil.rmtree(folder)
    os.makedirs(folder)
    dex_cfg = folder + "/dex.yaml"
    with open(dex_cfg, "w") as f:
        f.write(f"""issuer: {DEX_ISSUER}
storage:
  type: memory
web:
  http: 127.0.0.1:5560
telemetry:
  http: 127.0.0.1:5561
oauth2:
  skipApprovalScreen: true
staticClients:
- id: komboe
  redirectURIs:
  - '{WEB}/identity/connect/oidc-signin'
  name: Komboe
  secret: komboe-sso-secret
enablePasswordDB: true
staticPasswords:
- email: "{EMAIL}"
  hash: "{sso_dex.BCRYPT}"
  username: ada
  userID: "08a8684b-db88-4b73-90a9-3cd1661f5466"
  emailVerified: true
""")
    env = os.environ.copy()
    env.update({
        "DATA_FOLDER": folder,
        "ROCKET_PORT": "18443",
        "ROCKET_ADDRESS": "127.0.0.1",
        "DOMAIN": WEB,
        "SIGNUPS_ALLOWED": "true",
        "WEB_VAULT_ENABLED": "true",
        "WEB_VAULT_FOLDER": os.environ.get("KOMBOE_WEB_VAULT", "/workspace/clients/upstream/apps/web/build"),
        "SSO_ENABLED": "true",
        "SSO_AUTHORITY": DEX_ISSUER,
        "SSO_CLIENT_ID": "komboe",
        "SSO_CLIENT_SECRET": "komboe-sso-secret",
        "SSO_SIGNUPS_ALLOWED": "true",
        "SSO_ALLOW_UNKNOWN_EMAIL_VERIFICATION": "true",
        "LOGIN_RATELIMIT_MAX_BURST": "1000",
        "ROCKET_TLS": '{certs="%s/cert.pem",key="%s/key.pem"}' % ((os.environ.get("KOMBOE_TLS_DIR", "/tmp/komboe-tls"),) * 2),
    })
    procs = []
    try:
        procs.append(subprocess.Popen([DEX, "serve", dex_cfg], stdout=open(folder + "-dex.log", "w"), stderr=subprocess.STDOUT))
        sso_dex.wait_http(DEX_ISSUER + "/.well-known/openid-configuration")
        procs.append(subprocess.Popen([BIN], env=env, stdout=open(folder + "-vw.log", "w"), stderr=subprocess.STDOUT))
        sso_dex.wait_port(18443)
        time.sleep(0.5)
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(channel="chrome", headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
            page = browser.new_page(ignore_https_errors=True, viewport={"width": 1400, "height": 900})
            page.set_default_timeout(30000)
            sso(page)
            page.wait_for_function(
                "() => location.hash.includes('login-initiated') || location.hash.includes('vault') || location.hash.includes('setup-extension')",
                timeout=40000,
            )
            if "login-initiated" in page.url:
                page.get_by_role("button", name="Continue").click()
                page.wait_for_function(
                    "() => location.hash.includes('vault') || location.hash.includes('setup-extension')",
                    timeout=40000,
                )
            if "setup-extension" in page.url:
                page.get_by_role("button", name="Add it later").click()
                page.wait_for_timeout(800)
                page.get_by_role("link", name="Skip to web app").click()
            page.wait_for_function("() => location.hash.includes('vault')", timeout=20000)
            dismiss(page)
            page.locator("button").filter(has=page.locator("dynamic-avatar")).first.click()
            page.get_by_role("menuitem", name="Log out").or_(page.get_by_role("button", name="Log out")).first.click()
            page.wait_for_function("() => location.hash.includes('login')", timeout=20000)
            sso(page)
            page.wait_for_function(
                "() => location.hash.includes('vault') || location.hash.includes('setup-extension') || location.hash.includes('login-initiated')",
                timeout=40000,
            )
            assert "login-initiated" not in page.url, page.url
            assert page.locator("#masterPassword").count() == 0
            if "setup-extension" in page.url:
                page.get_by_role("button", name="Add it later").click()
                page.get_by_role("link", name="Skip to web app").click()
            page.wait_for_function("() => location.hash.includes('vault')", timeout=20000)
            browser.close()
        print("TRUSTED WEB PASS")
    finally:
        for proc in procs:
            proc.terminate()
        for proc in procs:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    main()
