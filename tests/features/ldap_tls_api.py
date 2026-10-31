#!/usr/bin/env python3
"""ldaps:// and StartTLS against a real slapd that refuses plaintext binds.

Proves: both TLS modes sync with the org's CA; an untrusted CA, no CA, or a hostname
that is not in the certificate is refused; plaintext ldap:// to the same server fails;
bad input (StartTLS with ldaps://, non-PEM CA) is rejected."""
import importlib.util
import os
import shutil
import subprocess
import time

here = os.path.dirname(__file__)
spec = importlib.util.spec_from_file_location("la", os.path.join(here, "ldap_api.py"))
la = importlib.util.module_from_spec(spec)
spec.loader.exec_module(la)
ft = la.ft

BASE = "http://127.0.0.1:18093"
PLAIN, TLSPORT = 1391, 1637
DN = "cn=admin,dc=komboe,dc=test"


def mkcert(folder, name, san=None, ca=None):
    key, crt = f"{folder}/{name}.key", f"{folder}/{name}.pem"
    if ca is None:
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "2", "-subj", f"/CN={name}",
                        "-keyout", key, "-out", crt], check=True, capture_output=True)
    else:
        csr = f"{folder}/{name}.csr"
        subprocess.run(["openssl", "req", "-newkey", "rsa:2048", "-nodes", "-subj", f"/CN={name}", "-keyout", key, "-out", csr],
                       check=True, capture_output=True)
        ext = f"{folder}/{name}.ext"
        open(ext, "w").write(f"subjectAltName={san}\nextendedKeyUsage=serverAuth\nbasicConstraints=CA:FALSE\n")
        subprocess.run(["openssl", "x509", "-req", "-in", csr, "-CA", f"{folder}/{ca}.pem", "-CAkey", f"{folder}/{ca}.key",
                        "-CAcreateserial", "-days", "2", "-extfile", ext, "-out", crt], check=True, capture_output=True)
    os.chmod(key, 0o600)
    return crt


def main():
    folder = "/tmp/komboe-ldaptls"
    if os.path.isdir(folder):
        shutil.rmtree(folder)
    os.makedirs(os.path.join(folder, "data"))
    ca = mkcert(folder, "test-ca")
    rogue = mkcert(folder, "rogue-ca")
    mkcert(folder, "server", san="IP:127.0.0.1", ca="test-ca")
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
    procs = []
    try:
        procs.append(subprocess.Popen(
            [*la.slapd_cmd(), "-f", f"{folder}/slapd.conf", "-h", f"ldap://127.0.0.1:{PLAIN}/ ldaps://127.0.0.1:{TLSPORT}/", "-d", "0"],
            stdout=open(folder + "-slapd.log", "w"), stderr=subprocess.STDOUT, env=la.slapd_env()))
        la.wait_port(PLAIN)
        la.wait_port(TLSPORT)
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
mail: ada-ldaptls@komboe.test
""")
        tenv = dict(la.slapd_env(), LDAPTLS_CACERT=ca)
        plain_add = subprocess.run([la.ldap_tool("ldapadd"), "-x", "-H", f"ldap://127.0.0.1:{PLAIN}", "-D", DN, "-w", la.BIND_PW, "-f", ldif],
                                   capture_output=True, text=True, env=tenv)
        assert plain_add.returncode != 0, "slapd must refuse plaintext binds for this test to mean anything"
        subprocess.run([la.ldap_tool("ldapadd"), "-ZZ", "-x", "-H", f"ldap://127.0.0.1:{PLAIN}", "-D", DN, "-w", la.BIND_PW, "-f", ldif],
                       check=True, capture_output=True, text=True, env=tenv)

        data = os.path.join(folder, "vw")
        os.makedirs(data)
        env = os.environ.copy()
        env.pop("SSL_CERT_FILE", None)
        env.update({"DATA_FOLDER": data, "ROCKET_PORT": "18093", "ROCKET_ADDRESS": "127.0.0.1", "DOMAIN": BASE,
                    "SIGNUPS_ALLOWED": "true", "WEB_VAULT_ENABLED": "false", "ORG_GROUPS_ENABLED": "true",
                    "LOGIN_RATELIMIT_MAX_BURST": "1000"})
        procs.append(subprocess.Popen([la.BIN], env=env, stdout=open(folder + "-vw.log", "w"), stderr=subprocess.STDOUT))
        la.wait_port(18093)
        time.sleep(0.3)
        ft.URL = BASE
        oid, _, _ = ft.org()
        owner = ft.a()
        ca_pem, rogue_pem = open(ca).read(), open(rogue).read()

        def put(url, start_tls=False, tls_ca=""):
            owner.api("PUT", f"/api/organizations/{oid}/ldap", {
                "url": url, "bindDn": DN, "bindPassword": la.BIND_PW, "userBase": "ou=people,dc=komboe,dc=test",
                "userFilter": "(objectClass=inetOrgPerson)", "emailAttr": "mail", "groupBase": "",
                "startTls": start_tls, "tlsCa": tls_ca})

        def sync_ok():
            return owner.api("POST", f"/api/organizations/{oid}/ldap/sync")

        def sync_fails(why):
            try:
                r = sync_ok()
            except ft.HTTPErr as e:
                assert e.code == 400, (why, e.code)
                return e.body if hasattr(e, "body") else str(e)
            raise AssertionError(f"sync should fail: {why}: {r}")

        put(f"ldaps://127.0.0.1:{TLSPORT}", tls_ca=ca_pem)
        shown = owner.api("GET", f"/api/organizations/{oid}/ldap")
        assert shown["hasCaCert"] is True and shown["startTls"] is False, shown
        r = sync_ok(); assert r["users"] == 1, r
        print("ok ldaps:// with org CA synced", r)

        put(f"ldap://127.0.0.1:{PLAIN}", start_tls=True, tls_ca=ca_pem)
        r = sync_ok(); assert r["users"] == 1, r
        print("ok StartTLS with org CA synced", r)
        # An older client (the current admin page) omits startTls/tlsCa: stored TLS settings must survive.
        owner.api("PUT", f"/api/organizations/{oid}/ldap", {"url": f"ldap://127.0.0.1:{PLAIN}", "bindDn": DN,
                  "userBase": "ou=people,dc=komboe,dc=test", "groupBase": ""})
        shown = owner.api("GET", f"/api/organizations/{oid}/ldap")
        assert shown["startTls"] is True and shown["hasCaCert"] is True, shown
        r = sync_ok(); assert r["users"] == 1, r
        print("ok TLS settings kept when a client omits them")

        put(f"ldap://127.0.0.1:{PLAIN}", start_tls=False, tls_ca=ca_pem)
        print("ok plaintext refused:", sync_fails("plaintext bind to tls-only slapd"))
        put(f"ldaps://127.0.0.1:{TLSPORT}", tls_ca=rogue_pem)
        print("ok rogue CA refused:", sync_fails("ldaps with wrong CA"))
        put(f"ldap://127.0.0.1:{PLAIN}", start_tls=True, tls_ca=rogue_pem)
        print("ok StartTLS rogue CA refused:", sync_fails("starttls with wrong CA"))
        put(f"ldaps://127.0.0.1:{TLSPORT}", tls_ca="")
        print("ok no CA refused:", sync_fails("ldaps with only system roots"))
        put(f"ldaps://localhost:{TLSPORT}", tls_ca=ca_pem)
        print("ok hostname mismatch refused:", sync_fails("cert has only IP SAN"))

        for body, why in [({"startTls": True, "url": f"ldaps://127.0.0.1:{TLSPORT}"}, "starttls+ldaps"),
                          ({"tlsCa": "not a certificate"}, "bad pem")]:
            full = {"url": f"ldap://127.0.0.1:{PLAIN}", "bindDn": DN, "bindPassword": la.BIND_PW,
                    "userBase": "ou=people,dc=komboe,dc=test", **body}
            try:
                owner.api("PUT", f"/api/organizations/{oid}/ldap", full)
                raise AssertionError(f"accepted {why}")
            except ft.HTTPErr as e:
                assert e.code == 400, (why, e.code)
        print("LDAP TLS API PASS")
    finally:
        for p in procs:
            p.terminate()
        for p in procs:
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()


if __name__ == "__main__":
    main()
