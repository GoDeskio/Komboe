#!/usr/bin/env python3
"""SCIM 2.0 against the real Vaultwarden server.

Provisioning invites a member. Deprovisioning revokes the membership and does
not store a master-password hash, a user key, or an organization key.
"""
import importlib.util
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

spec = importlib.util.spec_from_file_location("ft", os.path.join(os.path.dirname(__file__), "run.py"))
ft = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ft)

BIN = os.environ.get("KOMBOE_BIN", "/workspace/server/upstream/target/release/vaultwarden")
BASE = "http://127.0.0.1:18091"


def wait_port(port, timeout=40):
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


def scim(method, path, token, body=None):
    data = None if body is None else json.dumps(body).encode()
    headers = {"Authorization": "Bearer " + token, "Accept": "application/scim+json"}
    if data is not None:
        headers["Content-Type"] = "application/scim+json"
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read()
            return resp.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        raw = e.read()
        parsed = json.loads(raw) if raw else None
        if e.code >= 400 and e.code != 409:
            raise SystemExit(f"SCIM {method} {path} -> {e.code}: {parsed or raw[:300]!r}")
        return e.code, parsed


def main():
    folder = "/tmp/komboe-scim"
    if os.path.isdir(folder):
        shutil.rmtree(folder)
    os.makedirs(folder)
    env = os.environ.copy()
    env.update({
        "DATA_FOLDER": folder,
        "ROCKET_PORT": "18091",
        "ROCKET_ADDRESS": "127.0.0.1",
        "DOMAIN": BASE,
        "SIGNUPS_ALLOWED": "true",
        "WEB_VAULT_ENABLED": "false",
        "ORG_GROUPS_ENABLED": "true",
        "LOGIN_RATELIMIT_MAX_BURST": "1000",
    })
    log = open(folder + ".log", "w")
    proc = subprocess.Popen([BIN], env=env, stdout=log, stderr=subprocess.STDOUT)
    try:
        wait_port(18091)
        time.sleep(0.3)
        ft.URL = BASE
        oid, _, _ = ft.org()
        owner = ft.a()
        created = owner.api("POST", f"/api/organizations/{oid}/scim/token")
        token = created["token"]
        assert token.startswith("komboe-scim-") and created["enabled"] is True
        status, cfg = scim("GET", "/scim/v2/ServiceProviderConfig", token)
        assert status == 200 and cfg["patch"]["supported"] is True
        assert cfg["changePassword"]["supported"] is False

        email = f"scim-{uuid.uuid4().hex[:8]}@komboe.test"
        status, user = scim("POST", "/scim/v2/Users", token, {
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
            "userName": email,
            "externalId": "ext-ada",
            "name": {"givenName": "Ada", "familyName": "Directory"},
            "active": True,
        })
        assert status == 201, user
        uid = user["id"]
        assert user["userName"] == email and user["active"] is True
        assert "key" not in user and "privateKey" not in json.dumps(user)

        status, listed = scim("GET", "/scim/v2/Users?" + urllib.parse.urlencode({"filter": f'userName eq "{email}"'}), token)
        assert status == 200 and listed["totalResults"] == 1 and listed["Resources"][0]["id"] == uid

        status, patched = scim("PATCH", f"/scim/v2/Users/{uid}", token, {
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
            "Operations": [{"op": "replace", "path": "active", "value": False}],
        })
        assert status == 200 and patched["active"] is False, patched
        status, _ = scim("DELETE", f"/scim/v2/Users/{uid}", token)
        assert status == 204
        status, again = scim("GET", f"/scim/v2/Users/{uid}", token)
        assert again["active"] is False

        status, restored = scim("POST", "/scim/v2/Users", token, {"userName": email, "active": True, "externalId": "ext-ada"})
        assert status == 201 and restored["id"] == uid and restored["active"] is True

        status, group = scim("POST", "/scim/v2/Groups", token, {
            "displayName": "Directory Readers",
            "externalId": "grp-1",
            "members": [{"value": uid}],
        })
        assert status == 201 and group["members"][0]["value"] == uid
        assert group["members"][0]["display"] == email
        gid = group["id"]
        status, replaced = scim("PUT", f"/scim/v2/Groups/{gid}", token, {
            "displayName": "Directory Readers",
            "externalId": "grp-1",
            "members": [],
        })
        assert replaced["members"] == []
        status, _ = scim("DELETE", f"/scim/v2/Groups/{gid}", token)
        assert status == 204

        bad = urllib.request.Request(BASE + "/scim/v2/Users", headers={"Authorization": "Bearer nope-not-a-real-token"})
        try:
            urllib.request.urlopen(bad)
            raise SystemExit("bad token was accepted")
        except urllib.error.HTTPError as e:
            assert e.code == 401, e.code

        db = sqlite3.connect(os.path.join(folder, "db.sqlite3"))
        row = db.execute(
            "select u.password_hash, u.private_key, u.akey, m.akey, m.reset_password_key, m.status "
            "from users u join users_organizations m on m.user_uuid = u.uuid where u.email = ?",
            (email,),
        ).fetchone()
        assert row, "provisioned user missing"
        assert row[0] in (None, b"") and not row[1] and not row[2]
        assert not row[3] and not row[4]
        blob = open(os.path.join(folder, "db.sqlite3"), "rb").read()
        wal = os.path.join(folder, "db.sqlite3-wal")
        if os.path.isfile(wal):
            blob += open(wal, "rb").read()
        assert token.encode() not in blob
        assert email.encode() in blob
        print("SCIM API PASS")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    main()
