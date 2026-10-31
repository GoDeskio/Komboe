#!/usr/bin/env python3
"""Directory sync against a real slapd. Member passwords are not stored."""
import importlib.util
import os
import shutil
import socket
import sqlite3
import subprocess
import time

spec = importlib.util.spec_from_file_location("ft", os.path.join(os.path.dirname(__file__), "run.py"))
ft = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ft)

# A relocated OpenLDAP (e.g. a Debian package unpacked with dpkg-deb -x) can be used without root.
SLAPD_ROOT = os.environ.get("KOMBOE_SLAPD_ROOT", "")
LDAP_TOOLS = os.environ.get("KOMBOE_LDAP_TOOLS", "")
SCHEMA_DIR = SLAPD_ROOT + "/etc/ldap/schema"
MODULE_DIR = SLAPD_ROOT + "/usr/lib/ldap"


def slapd_cmd():
    return [SLAPD_ROOT + "/usr/sbin/slapd"] if SLAPD_ROOT else ["slapd"]


def slapd_env():
    env = os.environ.copy()
    if SLAPD_ROOT:
        env["LD_LIBRARY_PATH"] = SLAPD_ROOT + "/usr/lib/x86_64-linux-gnu:" + env.get("LD_LIBRARY_PATH", "")
    return env


def ldap_tool(name):
    return os.path.join(LDAP_TOOLS, name) if LDAP_TOOLS else name

BIN = os.environ.get("KOMBOE_BIN", "/workspace/server/upstream/target/release/vaultwarden")
BASE = "http://127.0.0.1:18092"
LDAP_PORT = 1389
EMAIL = "ada-ldap@komboe.test"
USER_SECRET = "User-Secret-Value-Not-Stored"
BIND_PW = "Bind-Only-Secret"


def wait_port(port, timeout=30):
    end = time.time() + timeout
    while time.time() < end:
        s = socket.socket()
        s.settimeout(0.3)
        try:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return
        finally:
            s.close()
        time.sleep(0.2)
    raise SystemExit(f"port {port} did not open")


def ldap_add(folder, ldif):
    path = os.path.join(folder, "entry.ldif")
    with open(path, "w") as f:
        f.write(ldif)
    subprocess.run(
        [ldap_tool("ldapadd"), "-x", "-H", f"ldap://127.0.0.1:{LDAP_PORT}", "-D", "cn=admin,dc=komboe,dc=test", "-w", BIND_PW, "-f", path],
        check=True, capture_output=True, text=True,
    )


def main():
    folder = "/tmp/komboe-ldap"
    if os.path.isdir(folder):
        shutil.rmtree(folder)
    os.makedirs(os.path.join(folder, "data"))
    with open(os.path.join(folder, "slapd.conf"), "w") as f:
        f.write(f"""
include {SCHEMA_DIR}/core.schema
include {SCHEMA_DIR}/cosine.schema
include {SCHEMA_DIR}/inetorgperson.schema
pidfile {folder}/slapd.pid
argsfile {folder}/slapd.args
modulepath {MODULE_DIR}
moduleload back_mdb
database mdb
maxsize 1073741824
suffix "dc=komboe,dc=test"
rootdn "cn=admin,dc=komboe,dc=test"
rootpw {BIND_PW}
directory {folder}/data
index objectClass eq
""")
    procs = []
    try:
        slapd_log = open(folder + "-slapd.log", "w")
        procs.append(subprocess.Popen(
            [*slapd_cmd(), "-f", os.path.join(folder, "slapd.conf"), "-h", f"ldap://127.0.0.1:{LDAP_PORT}", "-d", "0"],
            stdout=slapd_log, stderr=subprocess.STDOUT, env=slapd_env(),
        ))
        wait_port(LDAP_PORT)
        ldap_add(folder, """dn: dc=komboe,dc=test
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
mail: ada-ldap@komboe.test
userPassword: User-Secret-Value-Not-Stored

dn: cn=readers,ou=groups,dc=komboe,dc=test
objectClass: groupOfNames
cn: readers
member: uid=ada,ou=people,dc=komboe,dc=test
""")
        data = os.path.join(folder, "vw")
        os.makedirs(data)
        env = os.environ.copy()
        env.update({
            "DATA_FOLDER": data,
            "ROCKET_PORT": "18092",
            "ROCKET_ADDRESS": "127.0.0.1",
            "DOMAIN": BASE,
            "SIGNUPS_ALLOWED": "true",
            "WEB_VAULT_ENABLED": "false",
            "ORG_GROUPS_ENABLED": "true",
            "LOGIN_RATELIMIT_MAX_BURST": "1000",
        })
        vw_log = open(folder + "-vw.log", "w")
        procs.append(subprocess.Popen([BIN], env=env, stdout=vw_log, stderr=subprocess.STDOUT))
        wait_port(18092)
        time.sleep(0.3)
        ft.URL = BASE
        oid, _, _ = ft.org()
        owner = ft.a()
        owner.api("PUT", f"/api/organizations/{oid}/ldap", {
            "url": f"ldap://127.0.0.1:{LDAP_PORT}",
            "bindDn": "cn=admin,dc=komboe,dc=test",
            "bindPassword": BIND_PW,
            "userBase": "ou=people,dc=komboe,dc=test",
            "userFilter": "(objectClass=inetOrgPerson)",
            "emailAttr": "mail",
            "groupBase": "ou=groups,dc=komboe,dc=test",
            "groupFilter": "(objectClass=groupOfNames)",
            "memberAttr": "member",
        })
        shown = owner.api("GET", f"/api/organizations/{oid}/ldap")
        assert shown.get("hasPassword") is True and BIND_PW not in str(shown), "GET must not return the bind password"
        synced = owner.api("POST", f"/api/organizations/{oid}/ldap/sync")
        assert synced["users"] == 1 and synced["groups"] == 1, synced
        members = owner.api("GET", f"/api/organizations/{oid}/users")
        ada = next(m for m in members["data"] if m.get("email") == EMAIL or (m.get("user") or {}).get("email") == EMAIL)
        assert ada["status"] in (0, 1, 2), ada

        subprocess.run(
            [ldap_tool("ldapdelete"), "-x", "-H", f"ldap://127.0.0.1:{LDAP_PORT}", "-D", "cn=admin,dc=komboe,dc=test", "-w", BIND_PW,
             "uid=ada,ou=people,dc=komboe,dc=test"],
            check=True, capture_output=True, text=True,
        )
        # groupOfNames requires a member; remove the group before the user is already gone.
        again = owner.api("POST", f"/api/organizations/{oid}/ldap/sync")
        assert again["users"] == 0 and again["revoked"] == 1, again

        db = sqlite3.connect(os.path.join(data, "db.sqlite3"))
        row = db.execute(
            "select password_hash, private_key, akey from users where email = ?",
            (EMAIL,),
        ).fetchone()
        assert row and row[0] in (None, b"") and not row[1] and not row[2], "LDAP must not store a master-password hash or vault key"
        sealed = db.execute("select bind_password from komboe_ldap_configs").fetchone()[0]
        assert sealed.startswith("kv1:") and BIND_PW not in sealed, "bind password must be sealed at rest"
        member = db.execute(
            "select uo.akey, uo.reset_password_key, uo.status from users_organizations uo "
            "join users u on u.uuid = uo.user_uuid where u.email = ?",
            (EMAIL,),
        ).fetchone()
        assert member and not member[0] and not member[1] and member[2] < 0, member
        blob = open(os.path.join(data, "db.sqlite3"), "rb").read()
        wal = os.path.join(data, "db.sqlite3-wal")
        if os.path.isfile(wal):
            blob += open(wal, "rb").read()
        assert USER_SECRET.encode() not in blob
        assert BIND_PW.encode() not in blob, "bind password plaintext found in the database"
        print("LDAP API PASS")
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
