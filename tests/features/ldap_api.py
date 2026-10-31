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
        ["ldapadd", "-x", "-H", f"ldap://127.0.0.1:{LDAP_PORT}", "-D", "cn=admin,dc=komboe,dc=test", "-w", BIND_PW, "-f", path],
        check=True, capture_output=True, text=True,
    )


def main():
    folder = "/tmp/komboe-ldap"
    if os.path.isdir(folder):
        shutil.rmtree(folder)
    os.makedirs(os.path.join(folder, "data"))
    with open(os.path.join(folder, "slapd.conf"), "w") as f:
        f.write(f"""
include /etc/ldap/schema/core.schema
include /etc/ldap/schema/cosine.schema
include /etc/ldap/schema/inetorgperson.schema
pidfile {folder}/slapd.pid
argsfile {folder}/slapd.args
modulepath /usr/lib/ldap
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
            ["slapd", "-f", os.path.join(folder, "slapd.conf"), "-h", f"ldap://127.0.0.1:{LDAP_PORT}", "-d", "0"],
            stdout=slapd_log, stderr=subprocess.STDOUT,
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
        synced = owner.api("POST", f"/api/organizations/{oid}/ldap/sync")
        assert synced["users"] == 1 and synced["groups"] == 1, synced
        members = owner.api("GET", f"/api/organizations/{oid}/users")
        ada = next(m for m in members["data"] if m.get("email") == EMAIL or (m.get("user") or {}).get("email") == EMAIL)
        assert ada["status"] in (0, 1, 2), ada

        subprocess.run(
            ["ldapdelete", "-x", "-H", f"ldap://127.0.0.1:{LDAP_PORT}", "-D", "cn=admin,dc=komboe,dc=test", "-w", BIND_PW,
             "uid=ada,ou=people,dc=komboe,dc=test"],
            check=True, capture_output=True, text=True,
        )
        # groupOfNames requires a member; remove the group before the user is already gone.
        again = owner.api("POST", f"/api/organizations/{oid}/ldap/sync")
        assert again["users"] == 0 and again["revoked"] == 1, again

        db = sqlite3.connect(os.path.join(data, "db.sqlite3"))
        row = db.execute(
            "select password_hash, private_key from users where email = ?",
            (EMAIL,),
        ).fetchone()
        assert row and row[0] in (None, b"") and not row[1]
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
