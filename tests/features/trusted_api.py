#!/usr/bin/env python3
"""Trusted-device unlock stores only ciphertext.

An SSO account with no master password wraps its user key to a device RSA key.
A later SSO login returns that ciphertext. The server database never holds the key.
"""
import base64
import hashlib
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


def sso_login(opener_factory, device_id, device_type="10"):
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
        "deviceType": device_type,
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
        # Only this web browser is trusted: no *other* device can approve a login.
        assert trusted["HasLoginApprovingDevice"] is False, trusted
        assert first["UserDecryptionOptions"]["TrustedDeviceOption"]["HasLoginApprovingDevice"] is False

        # A trusted Linux desktop app is a real approver for a new browser.
        desk = str(uuid.uuid4())
        dl = sso_login(None, desk, "8")
        ft.http("PUT", f"/api/devices/{desk}/keys", {"encryptedUserKey": enc_user, "encryptedPublicKey": enc_pub,
                "encryptedPrivateKey": enc_priv}, token=dl["access_token"], base=VW)
        newb = str(uuid.uuid4())
        assert sso_login(None, newb)["UserDecryptionOptions"]["TrustedDeviceOption"]["HasLoginApprovingDevice"] is True
        # The desktop does not count as its own approver when only it and a web browser are trusted.
        assert sso_login(None, desk, "8")["UserDecryptionOptions"]["TrustedDeviceOption"]["HasLoginApprovingDevice"] is False
        ft.http("POST", "/api/devices/untrust", {"devices": [desk]}, token=dl["access_token"], base=VW)
        assert sso_login(None, newb)["UserDecryptionOptions"]["TrustedDeviceOption"]["HasLoginApprovingDevice"] is False

        ft.http("POST", "/api/devices/untrust", {"devices": [device_id]}, token=second["access_token"], base=VW)
        third = sso_login(None, device_id)
        assert "EncryptedUserKey" not in third["UserDecryptionOptions"]["TrustedDeviceOption"]

        db = sqlite3.connect(os.path.join(folder, "db.sqlite3"))
        row = db.execute("select password_hash, akey from users where email = ?", (EMAIL,)).fetchone()
        assert row and row[0] in (None, b"") and not row[1]
        # No recovery backdoor: no org password-reset enrollment, no admin-approval request.
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
