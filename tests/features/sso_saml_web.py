#!/usr/bin/env python3
"""Web vault SAML SSO login, end to end in Chrome, against the real pysaml2 IdP.

Login page -> "Use single sign-on" -> IdP form -> signed Response -> ACS -> web vault sso-connector ->
token -> the vault asks the new SSO user to set a master password (the server holds no vault key).
"""
import importlib.util
import ssl
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("sso_saml", os.path.join(HERE, "sso_saml.py"))
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)
samlidp = S.samlidp
WEB_VAULT = os.environ.get("KOMBOE_WEB_VAULT", "/workspace/run/web-vault")
# The web client refuses plain-http server URLs, so serve TLS with the local test cert.
TLS = os.environ.get("KOMBOE_TLS_DIR", "/workspace/run/tls")
S.VW = f"https://localhost:{S.PORT}"
SHOTS = os.environ.get("KOMBOE_SHOTS", "/tmp/komboe-saml-web")


def main():
    import ssl  # noqa
    ssl._create_default_https_context = ssl._create_unverified_context
    from playwright.sync_api import sync_playwright
    folder = tempfile.mkdtemp(prefix="komboe-saml-web-")
    os.makedirs(SHOTS, exist_ok=True)
    key, crt = samlidp.make_keypair(folder, "idp")
    idp_base = f"http://127.0.0.1:{S.IDP_PORT}"
    data = os.path.join(folder, "data")
    os.makedirs(data)
    env = os.environ.copy()
    env.update({
        "DATA_FOLDER": data, "ROCKET_PORT": str(S.PORT), "ROCKET_ADDRESS": "127.0.0.1", "DOMAIN": S.VW,
        "SIGNUPS_ALLOWED": "true", "WEB_VAULT_ENABLED": "true", "WEB_VAULT_FOLDER": WEB_VAULT,
        "SSO_ENABLED": "true", "SSO_SAML_ENABLED": "true", "SSO_SAML_IDP_ENTITY_ID": idp_base + "/metadata",
        "SSO_SAML_IDP_SSO_URL": idp_base + "/sso/redirect", "SSO_SAML_IDP_CERT": crt,
        "SSO_SAML_EMAIL_VERIFIED": "true", "SSO_SIGNUPS_ALLOWED": "true", "SSO_PKCE": "true",
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
            page = br.new_page(ignore_https_errors=True)
            if os.environ.get("DEBUG"):
                page.on("request", lambda r: print("REQ", r.method, r.url[:160]) if "/identity" in r.url or "/api" in r.url else None)
                page.on("console", lambda m: print("CONSOLE", m.type, m.text[:200]) if m.type in ("error", "warning") else None)
            try:
                page.goto(S.VW + "/#/login", wait_until="domcontentloaded")
                page.locator("input[type=email], input#login_input_email, input[formcontrolname=email]").first.fill(S.EMAIL)
                page.get_by_role("button", name="Use single sign-on").click(timeout=30000)
                # Single-IdP server: the vault may skip the identifier form and redirect straight away.
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
                        page.wait_for_url(idp_base + "/**", timeout=30000)
                        break
                    page.wait_for_timeout(500)
                page.wait_for_selector("input[name=username]", timeout=30000)
                page.fill("input[name=username]", S.EMAIL)
                page.fill("input[name=password]", S.PASSWORD)
                page.click("button")
                page.wait_for_url(lambda u: u.startswith(S.VW) and "sso-connector" not in u
                                  and "saml" not in u, timeout=60000)
                page.wait_for_timeout(5000)
                page.screenshot(path=os.path.join(SHOTS, "after-sso.png"))
                body = page.inner_text("body")
                print("landed:", page.url)
                # A brand-new SSO user without keys lands on the post-SSO "Logged in!" device screen
                # (or set-initial-password); either way the token exchange succeeded with no vault key on the server.
                assert any(k in page.url for k in ("login-initiated", "set-initial-password")), (page.url, body[:600])
                assert "Logged in" in body or "master password" in body.lower(), body[:600]
            except Exception:
                page.screenshot(path=os.path.join(SHOTS, "fail.png"))
                print("url at failure:", page.url)
                raise
            br.close()
        db = sqlite3.connect(os.path.join(data, "db.sqlite3"))
        row = db.execute("select password_hash, private_key, akey from users where email=?", (S.EMAIL,)).fetchone()
        assert row and not row[0] and row[1] is None and not row[2], "server must hold no vault key after SSO"
        assert db.execute("select count(*) from devices").fetchone()[0] >= 1
        print("SSO SAML WEB PASS")
    finally:
        if idp:
            idp.stop()
        vw.terminate()
        vw.wait(timeout=10)
        if os.environ.get("KEEP") != "1":
            shutil.rmtree(folder, ignore_errors=True)


if __name__ == "__main__":
    main()
