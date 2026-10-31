#!/usr/bin/env python3
"""Trusted-device unlock stores only ciphertext.

An SSO account with no master password wraps its user key to a device RSA key.
A later SSO login returns that ciphertext. The server database never holds the key.
"""
import base64
import hashlib
import html
import re
import http.cookiejar
import importlib.util
import json
import os
import shutil
import sqlite3
import subprocess
import time
import urllib.parse
import urllib.request
import uuid

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

spec = importlib.util.spec_from_file_location("ft", os.path.join(os.path.dirname(__file__), "run.py"))
ft = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ft)
sso = importlib.util.spec_from_file_location("sso_dex", os.path.join(os.path.dirname(__file__), "sso_dex.py"))
sso_dex = importlib.util.module_from_spec(sso)
sso.loader.exec_module(sso_dex)

BIN = os.environ.get("KOMBOE_BIN", "/workspace/server/upstream/target/release/vaultwarden")
DEX = os.environ.get("KOMBOE_DEX_BIN", "/tmp/dex-bin/dex")
VW = "http://127.0.0.1:18093"
DEX_ISSUER = "http://127.0.0.1:5557/dex"
EMAIL = "ada@komboe.test"


def sso_login(opener_factory, device_id):
    verifier = base64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    state = uuid.uuid4().hex
    qs = urllib.parse.urlencode({
        "client_id": "web",
        "redirect_uri": VW + "/sso-connector.html",
        "response_type": "code",
        "scope": "api offline_access",
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    })
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar), sso_dex.NoRedirect)
    landed = sso_dex.login_at_dex(opener, VW + "/identity/connect/authorize?" + qs)
    q = urllib.parse.parse_qs(urllib.parse.urlparse(landed).query)
    login = ft.http("POST", "/identity/connect/token", form={
        "grant_type": "authorization_code",
        "client_id": "web",
        "code": q["code"][0],
        "code_verifier": verifier,
        "scope": "api offline_access",
        "deviceType": "10",
        "deviceIdentifier": device_id,
        "deviceName": "trusted-browser",
    }, base=VW)
    return login


def main():
    if not os.path.isfile(DEX):
        raise SystemExit(f"dex binary missing: {DEX}")
    folder = "/tmp/komboe-trusted"
    if os.path.isdir(folder):
        shutil.rmtree(folder)
    os.makedirs(folder)
    dex_cfg = folder + "/dex.yaml"
    with open(dex_cfg, "w") as f:
        f.write(f"""issuer: {DEX_ISSUER}
storage:
  type: memory
web:
  http: 127.0.0.1:5557
telemetry:
  http: 127.0.0.1:5559
oauth2:
  skipApprovalScreen: true
staticClients:
- id: komboe
  redirectURIs:
  - '{VW}/identity/connect/oidc-signin'
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
    procs = []
    try:
        procs.append(subprocess.Popen([DEX, "serve", dex_cfg], stdout=open(folder + "-dex.log", "w"), stderr=subprocess.STDOUT))
        sso_dex.wait_http(DEX_ISSUER + "/.well-known/openid-configuration")
        env = os.environ.copy()
        env.update({
            "DATA_FOLDER": folder,
            "ROCKET_PORT": "18093",
            "ROCKET_ADDRESS": "127.0.0.1",
            "DOMAIN": VW,
            "SIGNUPS_ALLOWED": "true",
            "WEB_VAULT_ENABLED": "false",
            "SSO_ENABLED": "true",
            "SSO_AUTHORITY": DEX_ISSUER,
            "SSO_CLIENT_ID": "komboe",
            "SSO_CLIENT_SECRET": "komboe-sso-secret",
            "SSO_SIGNUPS_ALLOWED": "true",
            "SSO_ALLOW_UNKNOWN_EMAIL_VERIFICATION": "true",
            "LOGIN_RATELIMIT_MAX_BURST": "1000",
            # Mail on (Mailpit), so reset paths can't be refused merely for "email disabled".
            "SMTP_HOST": "127.0.0.1",
            "SMTP_PORT": os.environ.get("KOMBOE_MAILPIT_SMTP_PORT", "1025"),
            "SMTP_SECURITY": "off",
            "SMTP_FROM": "vault@komboe.test",
        })
        procs.append(subprocess.Popen([BIN], env=env, stdout=open(folder + "-vw.log", "w"), stderr=subprocess.STDOUT))
        sso_dex.wait_port(18093)
        time.sleep(0.4)
        ft.URL = VW
        device_id = str(uuid.uuid4())
        first = sso_login(None, device_id)
        assert first.get("access_token"), first
        options = first["UserDecryptionOptions"]
        assert options["HasMasterPassword"] is False
        assert "EncryptedUserKey" not in options["TrustedDeviceOption"]
        assert "KeyConnectorOption" not in options

        user_key = os.urandom(64)
        priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        wrapped = priv.public_key().encrypt(
            user_key,
            padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA1()), algorithm=hashes.SHA1(), label=None),
        )
        enc_user = "4." + base64.b64encode(wrapped).decode()
        enc_pub = "2." + base64.b64encode(os.urandom(16)).decode() + "|bb|cc"
        enc_priv = "2." + base64.b64encode(os.urandom(16)).decode() + "|dd|ee"
        saved = ft.http("PUT", f"/api/devices/{device_id}/keys", {
            "encryptedUserKey": enc_user,
            "encryptedPublicKey": enc_pub,
            "encryptedPrivateKey": enc_priv,
        }, token=first["access_token"], base=VW)
        assert saved["isTrusted"] is True

        second = sso_login(None, device_id)
        trusted = second["UserDecryptionOptions"]["TrustedDeviceOption"]
        assert second["UserDecryptionOptions"]["HasMasterPassword"] is False
        assert trusted["EncryptedUserKey"] == enc_user
        assert trusted["EncryptedPrivateKey"] == enc_priv
        assert trusted["HasAdminApproval"] is False
        got = priv.decrypt(
            base64.b64decode(trusted["EncryptedUserKey"][2:]),
            padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA1()), algorithm=hashes.SHA1(), label=None),
        )
        assert got == user_key

        ft.http("POST", "/api/devices/untrust", {"devices": [device_id]}, token=second["access_token"], base=VW)
        third = sso_login(None, device_id)
        assert "EncryptedUserKey" not in third["UserDecryptionOptions"]["TrustedDeviceOption"]

        # Real org membership: an owner's org with Ada as a confirmed member. Every reset path must stay shut.
        oid, ok, oaep = ft.org()
        owner = ft.S["a"]
        owner.api("POST", f"/api/organizations/{oid}/users/invite", {"emails": [EMAIL], "type": 2, "collections": [],
                  "accessAll": False, "permissions": {}, "groups": []})
        ada_tok = sso_login(None, device_id)["access_token"]
        mem = next(m for m in owner.api("GET", f"/api/organizations/{oid}/users")["data"] if m["email"] == EMAIL)
        if mem["status"] == 0:  # Ada accepts with the token from the real invite mail (Mailpit)
            m = ft.mailpit(EMAIL, "Join")
            tok = re.search(r"token=([^&\"'\s<]+)", m["Text"] + m["HTML"]).group(1)
            ft.http("POST", f"/api/organizations/{oid}/users/{mem['id']}/accept",
                    {"token": html.unescape(urllib.parse.unquote(tok)), "resetPasswordKey": None}, token=ada_tok, base=VW)
        owner.api("POST", f"/api/organizations/{oid}/users/{mem['id']}/confirm", {"key": "4." + base64.b64encode(os.urandom(256)).decode()})
        mem = next(m for m in owner.api("GET", f"/api/organizations/{oid}/users")["data"] if m["email"] == EMAIL)
        assert mem["status"] == 2, mem  # confirmed
        assert mem.get("resetPasswordEnrolled") in (False, None), mem
        ada_sync = ft.http("GET", "/api/sync", token=ada_tok, base=VW)
        ada_org = next(o for o in ada_sync["profile"]["organizations"] if o["id"] == oid)
        assert ada_org["resetPasswordEnrolled"] is False and ada_org.get("useResetPassword") in (False, None), ada_org
        refused = {}
        def must_fail(name, fn):
            try:
                fn()
            except ft.HTTPErr as e:
                refused[name] = e.code
                return
            raise AssertionError(f"reset path open: {name}")
        reset_key = "4." + base64.b64encode(os.urandom(256)).decode()
        must_fail("enable account-recovery policy", lambda: owner.api("PUT", f"/api/organizations/{oid}/policies/8",
                  {"type": 8, "enabled": True, "data": {"autoEnrollEnabled": True}}))
        must_fail("member enrolls reset key", lambda: ft.http("PUT", f"/api/organizations/{oid}/users/{ada_sync['profile']['id']}/reset-password-enrollment",
                  {"resetPasswordKey": reset_key, "masterPasswordHash": None}, token=ada_tok, base=VW))
        must_fail("owner reads reset details", lambda: owner.api("GET", f"/api/organizations/{oid}/users/{mem['id']}/reset-password-details"))
        must_fail("owner resets password", lambda: owner.api("PUT", f"/api/organizations/{oid}/users/{mem['id']}/reset-password",
                  {"newMasterPasswordHash": "x" * 44, "key": "2.aa|bb|cc"}))
        must_fail("admin-approval auth request", lambda: ft.http("POST", "/api/auth-requests/admin-request", {"email": EMAIL,
                  "publicKey": base64.b64encode(os.urandom(32)).decode(), "deviceIdentifier": device_id, "accessCode": "x" * 25,
                  "type": 2}, token=ada_tok, base=VW))
        member_login = sso_login(None, device_id)["UserDecryptionOptions"]
        tdo = member_login["TrustedDeviceOption"]
        assert tdo["HasAdminApproval"] is False and tdo["HasManageResetPasswordPermission"] is False, tdo
        assert "KeyConnectorOption" not in member_login
        pols = owner.api("GET", f"/api/organizations/{oid}/policies")["data"]
        assert not any(p["type"] == 8 and p["enabled"] for p in pols), pols
        print("RESET PATHS REFUSED", json.dumps(refused))

        db = sqlite3.connect(os.path.join(folder, "db.sqlite3"))
        row = db.execute("select password_hash, akey from users where email = ?", (EMAIL,)).fetchone()
        assert row and row[0] in (None, b"") and not row[1]
        # No recovery backdoor: no org password-reset enrollment, no admin-approval request.
        status = db.execute("select uo.status from users_organizations uo join users u on u.uuid = uo.user_uuid where u.email = ?",
                            (EMAIL,)).fetchone()
        assert status and status[0] == 2, status  # a real confirmed membership exists
        resets = db.execute(
            "select count(*) from users_organizations uo join users u on u.uuid = uo.user_uuid "
            "where u.email = ? and uo.reset_password_key is not null and uo.reset_password_key != ''",
            (EMAIL,),
        ).fetchone()[0]
        assert resets == 0, resets
        assert trusted.get("HasManageResetPasswordPermission") is False
        assert "KeyConnectorOption" not in second["UserDecryptionOptions"]
        blob = open(os.path.join(folder, "db.sqlite3"), "rb").read()
        wal = os.path.join(folder, "db.sqlite3-wal")
        if os.path.isfile(wal):
            blob += open(wal, "rb").read()
        assert user_key not in blob
        print("TRUSTED DEVICE PASS")
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
