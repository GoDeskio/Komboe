#!/usr/bin/env python3
"""Web vault "Log out" triggers SAML single logout, end to end in Chrome against the pysaml2 IdP.

SAML sign-in through the vault -> account menu -> Log out -> the vault wipes local keys, the server ends every
session (devices deleted) and the browser lands on the IdP SLO URL with a signed LogoutRequest for the user.
"""
import base64
import importlib.util
import os
import shutil
import sqlite3
import ssl
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("sso_saml", os.path.join(HERE, "sso_saml.py"))
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)
samlidp = S.samlidp
WEB_VAULT = os.environ.get("KOMBOE_WEB_VAULT", "/workspace/run/web-vault")
TLS = os.environ.get("KOMBOE_TLS_DIR", "/workspace/run/tls")
S.VW = f"https://localhost:{S.PORT}"
SHOTS = os.environ.get("KOMBOE_SHOTS", "/tmp/komboe-saml-slo-web")


def continue_to_vault(page):
    page.wait_for_function("() => /login-initiated|vault|setup-extension|set-initial-password/.test(location.hash)", timeout=60000)
    if "login-initiated" in page.url:
        page.get_by_role("button", name="Continue").click()
        page.wait_for_function("() => /vault|setup-extension/.test(location.hash)", timeout=40000)
    if "setup-extension" in page.url:
        page.get_by_role("button", name="Add it later").click()
        page.wait_for_timeout(800)
        page.get_by_role("link", name="Skip to web app").click()
    page.wait_for_function("() => location.hash.includes('vault')", timeout=30000)
    for name in ("Skip", "Add it later", "Close"):
        b = page.locator(".cdk-overlay-container").get_by_role("button", name=name)
        if b.count():
            b.first.click()
            page.wait_for_timeout(300)


def main():
    ssl._create_default_https_context = ssl._create_unverified_context
    from playwright.sync_api import sync_playwright
    folder = tempfile.mkdtemp(prefix="komboe-saml-slo-web-")
    os.makedirs(SHOTS, exist_ok=True)
    key, crt = samlidp.make_keypair(folder, "idp")
    sp_key, sp_crt = samlidp.make_keypair(folder, "sp")
    idp_base = f"http://127.0.0.1:{S.IDP_PORT}"
    data = os.path.join(folder, "data")
    os.makedirs(data)
    env = os.environ.copy()
    env.update({
        "DATA_FOLDER": data, "ROCKET_PORT": str(S.PORT), "ROCKET_ADDRESS": "127.0.0.1", "DOMAIN": S.VW,
        "SIGNUPS_ALLOWED": "true", "WEB_VAULT_ENABLED": "true", "WEB_VAULT_FOLDER": WEB_VAULT,
        "SSO_ENABLED": "true", "SSO_SAML_ENABLED": "true", "SSO_SAML_IDP_ENTITY_ID": idp_base + "/metadata",
        "SSO_SAML_IDP_SSO_URL": idp_base + "/sso/redirect", "SSO_SAML_IDP_CERT": crt,
        "SSO_SAML_IDP_SLO_URL": idp_base + "/slo", "SSO_SAML_SP_KEY": sp_key, "SSO_SAML_SP_CERT": sp_crt,
        "SSO_SAML_EMAIL_VERIFIED": "true", "SSO_SIGNUPS_ALLOWED": "true", "SSO_PKCE": "true",
        "LOGIN_RATELIMIT_MAX_BURST": "1000",
        "ROCKET_TLS": '{certs="%s/cert.pem",key="%s/key.pem"}' % (TLS, TLS),
    })
    vw = subprocess.Popen([S.BIN], env=env, stdout=open(os.path.join(folder, "vw.log"), "w"), stderr=subprocess.STDOUT)
    idp = None
    try:
        S.dex.wait_port(S.PORT)
        time.sleep(0.4)
        md = urllib.request.urlopen(S.VW + "/identity/saml/metadata", timeout=10, context=ssl._create_unverified_context()).read().decode()
        md_file = os.path.join(folder, "sp.xml")
        open(md_file, "w").write(md)
        idp = samlidp.IdP(S.IDP_PORT, key, crt, md_file, {S.EMAIL: {"password": S.PASSWORD, "name": S.NAME}}).start()
        with sync_playwright() as p:
            br = p.chromium.launch(channel="chrome", headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
            page = br.new_page(ignore_https_errors=True, viewport={"width": 1400, "height": 900})
            page.set_default_timeout(30000)
            if os.environ.get("DEBUG"):
                page.on("console", lambda m: print("CONSOLE", m.type, m.text[:300]))
                page.on("framenavigated", lambda f: print("NAV", f.url[:200]) if f == page.main_frame else None)
            try:
                page.goto(S.VW + "/#/login", wait_until="domcontentloaded")
                page.locator("input[type=email], input#login_input_email, input[formcontrolname=email]").first.fill(S.EMAIL)
                page.get_by_role("button", name="Use single sign-on").click()
                ident = page.get_by_label("SSO identifier")
                for _ in range(60):
                    if page.url.startswith(idp_base):
                        break
                    if ident.count() and ident.is_visible() and ident.is_enabled():
                        page.wait_for_timeout(1000)
                        if page.url.startswith(idp_base):
                            break
                        ident.fill("komboe")
                        page.get_by_role("button", name="Continue").click()
                        break
                    page.wait_for_timeout(500)
                page.wait_for_selector("input[name=username]")
                page.fill("input[name=username]", S.EMAIL)
                page.fill("input[name=password]", S.PASSWORD)
                page.click("button")
                continue_to_vault(page)
                page.screenshot(path=os.path.join(SHOTS, "vault.png"))
                db = sqlite3.connect(os.path.join(data, "db.sqlite3"))
                assert db.execute("select count(*) from devices").fetchone()[0] >= 1

                print("=== LOGOUT CLICK")
                page.locator("button").filter(has=page.locator("dynamic-avatar")).first.click()
                page.get_by_role("menuitem", name="Log out").or_(page.get_by_role("button", name="Log out")).first.click()
                page.wait_for_url(idp_base + "/slo?**", timeout=30000)
                page.screenshot(path=os.path.join(SHOTS, "idp-slo.png"))
            except Exception:
                page.screenshot(path=os.path.join(SHOTS, "fail.png"))
                print("url at failure:", page.url)
                raise
            q = urllib.parse.parse_qs(urllib.parse.urlparse(page.url).query)
            xml = zlib.decompress(base64.b64decode(q["SAMLRequest"][0]), -15).decode()
            assert "LogoutRequest" in xml and S.EMAIL in xml, xml
            assert q.get("SigAlg") and q.get("Signature"), "LogoutRequest redirect must be signed"
            print("  browser sent to IdP SLO with a signed LogoutRequest for", S.EMAIL)
            assert db.execute("select count(*) from devices").fetchone()[0] == 0, "server sessions not ended"
            print("  server ended all sessions (devices removed)")
            # Local state is wiped: the vault no longer opens without signing in again.
            page.goto(S.VW + "/#/vault", wait_until="domcontentloaded")
            page.wait_for_function("() => /login|lock/.test(location.hash) && !location.hash.includes('vault')", timeout=30000)
            assert "lock" not in page.url, "logout must clear the account, not just lock it: " + page.url
            print("  vault requires a fresh sign-in:", page.url)
            br.close()
        print("SSO SAML SLO WEB PASS")
    finally:
        if idp:
            idp.stop()
        vw.terminate()
        vw.wait(timeout=10)
        if os.environ.get("KEEP") != "1":
            shutil.rmtree(folder, ignore_errors=True)


if __name__ == "__main__":
    main()
