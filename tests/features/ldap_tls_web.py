#!/usr/bin/env python3
"""Org admin configures StartTLS + a CA certificate for a TLS-only slapd from the web vault.

Proves: the Directory page has StartTLS and CA fields, a sync over StartTLS with the pasted CA
succeeds against a slapd that refuses plaintext binds, the settings persist after a reload
(CA kept when the field is left empty), and the bind password eye toggle still works."""
import importlib.util
import os
import shutil
import subprocess

here = os.path.dirname(__file__)
def _load(name, file):
    s = importlib.util.spec_from_file_location(name, os.path.join(here, file))
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m
lt = _load("ldap_tls_api", "ldap_tls_api.py")
la, ft = lt.la, lt.ft

WEB = os.environ.get("KOMBOE_WEB") or os.environ.get("KOMBOE_URL") or "https://127.0.0.1:8443"
PORT = 1394
DN = lt.DN


def main():
    import ssl
    ssl._create_default_https_context = ssl._create_unverified_context
    from playwright.sync_api import sync_playwright
    folder = "/tmp/komboe-ldaptls-web"
    if os.path.isdir(folder):
        shutil.rmtree(folder)
    os.makedirs(os.path.join(folder, "data"))
    ca = lt.mkcert(folder, "test-ca")
    lt.mkcert(folder, "server", san="IP:127.0.0.1", ca="test-ca")
    with open(os.path.join(folder, "slapd.conf"), "w") as f:
        f.write(f"""
include {la.SCHEMA_DIR}/core.schema
include {la.SCHEMA_DIR}/cosine.schema
include {la.SCHEMA_DIR}/inetorgperson.schema
pidfile {folder}/slapd.pid
argsfile {folder}/slapd.args
modulepath {la.MODULE_DIR}
moduleload back_mdb
TLSCACertificateFile {ca}
TLSCertificateFile {folder}/server.pem
TLSCertificateKeyFile {folder}/server.key
security tls=1
database mdb
maxsize 1073741824
suffix "dc=komboe,dc=test"
rootdn "{DN}"
rootpw {la.BIND_PW}
directory {folder}/data
index objectClass eq
""")
    proc = subprocess.Popen([*la.slapd_cmd(), "-f", f"{folder}/slapd.conf", "-h", f"ldap://127.0.0.1:{PORT}/", "-d", "0"],
                            stdout=open(folder + "-slapd.log", "w"), stderr=subprocess.STDOUT, env=la.slapd_env())
    try:
        la.wait_port(PORT)
        ldif = f"{folder}/seed.ldif"
        open(ldif, "w").write("""dn: dc=komboe,dc=test
objectClass: dcObject
objectClass: organization
dc: komboe
o: Komboe

dn: ou=people,dc=komboe,dc=test
objectClass: organizationalUnit
ou: people

dn: uid=ada,ou=people,dc=komboe,dc=test
objectClass: inetOrgPerson
uid: ada
cn: Ada Directory
sn: Directory
mail: ada-ldaptlsweb@komboe.test
""")
        tenv = dict(la.slapd_env(), LDAPTLS_CACERT=ca)
        plain = subprocess.run([la.ldap_tool("ldapadd"), "-x", "-H", f"ldap://127.0.0.1:{PORT}", "-D", DN, "-w", la.BIND_PW, "-f", ldif],
                               capture_output=True, text=True, env=tenv)
        assert plain.returncode != 0, "slapd must refuse plaintext binds"
        subprocess.run([la.ldap_tool("ldapadd"), "-ZZ", "-x", "-H", f"ldap://127.0.0.1:{PORT}", "-D", DN, "-w", la.BIND_PW, "-f", ldif],
                       check=True, capture_output=True, text=True, env=tenv)
        oid, _, _ = ft.org()
        user = ft.a()
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
            skip = page.locator(".cdk-overlay-container").get_by_role("button", name="Skip")
            if skip.count():
                skip.click()
                page.wait_for_timeout(300)
            url = WEB + f"/#/organizations/{oid}/settings/directory"
            page.goto(url, wait_until="domcontentloaded")
            page.get_by_test_id("ldap-url").fill(f"ldap://127.0.0.1:{PORT}")
            page.get_by_test_id("ldap-bind-dn").fill(DN)
            page.get_by_test_id("ldap-bind-password").fill(la.BIND_PW)
            bind = page.get_by_test_id("ldap-bind-password")
            assert bind.get_attribute("type") == "password"
            page.locator("[bitpasswordinputtoggle]").click()
            assert bind.get_attribute("type") == "text", "eye toggle must reveal the bind password"
            page.locator("[bitpasswordinputtoggle]").click()
            assert bind.get_attribute("type") == "password"
            page.get_by_test_id("ldap-user-base").fill("ou=people,dc=komboe,dc=test")
            # Without StartTLS the TLS-only directory refuses the bind.
            page.get_by_test_id("ldap-sync").click()
            page.get_by_test_id("ldap-error").wait_for()
            page.get_by_test_id("ldap-start-tls").check()
            page.get_by_test_id("ldap-tls-ca").fill(open(ca).read())
            page.get_by_test_id("ldap-sync").click()
            page.get_by_test_id("ldap-result").wait_for()
            assert "users 1" in page.get_by_test_id("ldap-result").inner_text()
            assert page.get_by_test_id("ldap-tls-ca").input_value() == "", "CA field clears after save"
            page.reload(wait_until="domcontentloaded")
            page.get_by_test_id("ldap-ca-stored").wait_for()
            assert page.get_by_test_id("ldap-start-tls").is_checked(), "StartTLS must persist"
            page.get_by_test_id("ldap-sync").click()
            page.get_by_test_id("ldap-result").wait_for()
            assert "users 1" in page.get_by_test_id("ldap-result").inner_text(), "stored CA must be kept when field is empty"
            browser.close()
        print("LDAP TLS WEB PASS")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    main()
