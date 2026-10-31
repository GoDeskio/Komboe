#!/usr/bin/env python3
"""Two Vaultwarden processes share one Postgres database."""
import importlib.util, json, os, socket, subprocess, sys, time, urllib.request

spec = importlib.util.spec_from_file_location("ft", os.path.join(os.path.dirname(__file__), "run.py"))
ft = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ft)

BIN = os.environ.get("KOMBOE_HA_BIN", "/tmp/vw-pg/release/vaultwarden")
DBURL = os.environ.get("KOMBOE_PG_URL", "postgresql://komboe:komboe@127.0.0.1:5432/komboe_ha")
A = "http://127.0.0.1:18080"
B = "http://127.0.0.1:18081"


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
        time.sleep(0.3)
    raise SystemExit(f"port {port} did not open")


def start(port, folder):
    os.makedirs(folder, exist_ok=True)
    env = os.environ.copy()
    env.update({
        "DATA_FOLDER": folder,
        "DATABASE_URL": DBURL,
        "ROCKET_PORT": str(port),
        "ROCKET_ADDRESS": "127.0.0.1",
        "DOMAIN": f"http://127.0.0.1:{port}",
        "SIGNUPS_ALLOWED": "true",
        "WEB_VAULT_ENABLED": "false",
    })
    log = open(folder + ".log", "w")
    return subprocess.Popen([BIN], env=env, stdout=log, stderr=subprocess.STDOUT)


def main():
    if not os.path.isfile(BIN):
        raise SystemExit(f"postgres-enabled binary missing: {BIN}")
    procs = []
    try:
        procs = [start(18080, "/tmp/komboe-ha-a")]
        wait_port(18080)
        procs.append(start(18081, "/tmp/komboe-ha-b"))
        wait_port(18081)
        time.sleep(1)
        import uuid, hashlib, os as _os
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        email = f"ha-{uuid.uuid4().hex[:8]}@komboe.test"
        pw = "Komboe-HA-" + uuid.uuid4().hex
        it = 600_000
        mk = hashlib.pbkdf2_hmac("sha256", pw.encode(), email.encode(), it, 32)
        ph = ft.b64(hashlib.pbkdf2_hmac("sha256", mk, pw.encode(), 1, 32))
        uk = _os.urandom(64)
        priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pub = priv.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
        tok = ft.http("POST", "/identity/accounts/register/send-verification-email", {"email": email, "name": "HA"}, base=A)
        body = {"email": email, "emailVerificationToken": tok, "masterPasswordHash": ph, "kdf": 0, "kdfIterations": it,
                "userSymmetricKey": ft.enc(uk, ft.stretch(mk)),
                "userAsymmetricKeys": {"publicKey": ft.b64(pub), "encryptedPrivateKey": ft.enc(priv.private_bytes(
                    serialization.Encoding.DER, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()), uk)}}
        ft.http("POST", "/identity/accounts/register/finish", body, base=A)
        login = ft.http("POST", "/identity/connect/token", form={
            "grant_type": "password", "username": email, "password": ph, "scope": "api offline_access",
            "client_id": "web", "deviceType": "10", "deviceIdentifier": uuid.uuid4().hex, "deviceName": "ha-b",
        }, base=B)
        assert login.get("access_token"), login
        profile = ft.http("GET", "/api/accounts/profile", token=login["access_token"], base=B)
        assert profile["email"] == email, profile
        print("HA POSTGRES PASS")
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
