#!/usr/bin/env python3
"""An organization admin syncs a real slapd directory from the web vault."""
import importlib.util
import os
import shutil
import subprocess

spec = importlib.util.spec_from_file_location("ft", os.path.join(os.path.dirname(__file__), "run.py"))
ft = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ft)
la = importlib.util.spec_from_file_location("ldap_api", os.path.join(os.path.dirname(__file__), "ldap_api.py"))
ldap_api = importlib.util.module_from_spec(la)
la.loader.exec_module(ldap_api)

WEB = os.environ.get("KOMBOE_WEB") or os.environ.get("KOMBOE_URL") or "https://127.0.0.1:8443"


def main():
    import ssl
    ssl._create_default_https_context = ssl._create_unverified_context
    from playwright.sync_api import sync_playwright
    folder = "/tmp/komboe-ldap-web"
    if os.path.isdir(folder):
        shutil.rmtree(folder)
    os.makedirs(os.path.join(folder, "data"))
    with open(os.path.join(folder, "slapd.conf"), "w") as f:
        f.write(f"""
include {ldap_api.SCHEMA_DIR}/core.schema
include {ldap_api.SCHEMA_DIR}/cosine.schema
include {ldap_api.SCHEMA_DIR}/inetorgperson.schema
pidfile {folder}/slapd.pid
argsfile {folder}/slapd.args
modulepath {ldap_api.MODULE_DIR}
moduleload back_mdb
database mdb
maxsize 1073741824
suffix "dc=komboe,dc=test"
rootdn "cn=admin,dc=komboe,dc=test"
rootpw {ldap_api.BIND_PW}
directory {folder}/data
index objectClass eq
""")
    log = open(folder + "-slapd.log", "w")
    proc = subprocess.Popen(
        [*ldap_api.slapd_cmd(), "-f", os.path.join(folder, "slapd.conf"), "-h", f"ldap://127.0.0.1:{ldap_api.LDAP_PORT}", "-d", "0"],
        stdout=log, stderr=subprocess.STDOUT,
    )
    try:
        ldap_api.wait_port(ldap_api.LDAP_PORT)
        ldap_api.ldap_add(folder, f"""dn: dc=komboe,dc=test
objectClass: dcObject
objectClass: organization
dc: komboe
o: Komboe

dn: ou=people,dc=komboe,dc=test
objectClass: organizationalUnit
ou: people

dn: ou=groups,dc=komboe,dc=test
objectClass: organizationalUnit
ou: groups

dn: uid=ada,ou=people,dc=komboe,dc=test
objectClass: inetOrgPerson
uid: ada
cn: Ada Directory
sn: Directory
mail: {ldap_api.EMAIL}
userPassword: {ldap_api.USER_SECRET}

dn: cn=readers,ou=groups,dc=komboe,dc=test
objectClass: groupOfNames
cn: readers
member: uid=ada,ou=people,dc=komboe,dc=test
""")
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
            overlay = page.locator(".cdk-overlay-container")
            skip_tour = overlay.get_by_role("button", name="Skip")
            if skip_tour.count():
                skip_tour.click()
                page.wait_for_timeout(300)
            page.goto(WEB + f"/#/organizations/{oid}/settings/directory", wait_until="domcontentloaded")
            page.get_by_test_id("ldap-url").fill(f"ldap://127.0.0.1:{ldap_api.LDAP_PORT}")
            page.get_by_test_id("ldap-bind-dn").fill("cn=admin,dc=komboe,dc=test")
            page.get_by_test_id("ldap-bind-password").fill(ldap_api.BIND_PW)
            bind = page.get_by_test_id("ldap-bind-password")
            assert bind.get_attribute("type") == "password", "bind password must be masked by default"
            page.locator("[bitpasswordinputtoggle]").click()
            assert bind.get_attribute("type") == "text"
            page.locator("[bitpasswordinputtoggle]").click()
            assert bind.get_attribute("type") == "password", "eye toggle must re-hide the bind password"
            page.get_by_test_id("ldap-user-base").fill("ou=people,dc=komboe,dc=test")
            page.get_by_test_id("ldap-group-base").fill("ou=groups,dc=komboe,dc=test")
            page.get_by_test_id("ldap-sync").click()
            page.get_by_test_id("ldap-result").wait_for()
            text = page.get_by_test_id("ldap-result").inner_text()
            assert "users 1" in text and "groups 1" in text, text
            browser.close()
        print("LDAP WEB PASS")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    main()
