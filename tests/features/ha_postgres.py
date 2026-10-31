#!/usr/bin/env python3
"""Two Vaultwarden processes share one Postgres database (and one data folder for the JWT RSA key and attachments):
a token minted on A works on B, a write on B is read on A, and B keeps serving after A dies."""
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


SHARED = os.environ.get("KOMBOE_HA_DATA", "/tmp/komboe-ha-shared")


def start(port, folder):
    os.makedirs(folder, exist_ok=True)
    os.makedirs(SHARED, exist_ok=True)
    env = os.environ.copy()
    if os.environ.get("KOMBOE_PG_LIB"):
        env["LD_LIBRARY_PATH"] = os.environ["KOMBOE_PG_LIB"] + ":" + env.get("LD_LIBRARY_PATH", "")
    env.update({
        "DATA_FOLDER": SHARED,
        "RSA_KEY_FILENAME": os.path.join(SHARED, "rsa_key"),
        "DATABASE_URL": DBURL,
        "ROCKET_PORT": str(port),
        "ROCKET_ADDRESS": "127.0.0.1",
        "DOMAIN": os.environ.get("KOMBOE_HA_DOMAIN", "http://komboe-ha.test"),  # one public URL for all nodes (JWT issuer)
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
        import shutil
        shutil.rmtree(SHARED, ignore_errors=True)
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
            "client_id": "web", "deviceType": "10", "deviceIdentifier": uuid.uuid4().hex, "deviceName": "ha-a",
        }, base=A)
        tok = login["access_token"]
        import base64 as _b, json as _j
        seg = tok.split(".")[1]; uid = _j.loads(_b.urlsafe_b64decode(seg + "=" * (-len(seg) % 4)))["sub"]
        profile = ft.http("GET", "/api/accounts/profile", token=tok, base=B)  # token minted by A, accepted by B
        assert profile["email"] == email, profile
        name = ft.enc(b"ha-item", uk)
        cid = ft.http("POST", "/api/ciphers", {"type": 2, "name": name, "secureNote": {"type": 0}, "favorite": False,
                                                 "reprompt": 0, "notes": None, "organizationId": None, "encryptedFor": uid}, token=tok, base=B)["id"]
        seen = ft.http("GET", f"/api/ciphers/{cid}", token=tok, base=A)  # written on B, read on A
        assert seen["id"] == cid and seen["name"] == name, seen
        # Concurrent writes to both nodes all land.
        import concurrent.futures as cf
        def mk(i):
            base = A if i % 2 else B
            return ft.http("POST", "/api/ciphers", {"type": 2, "name": ft.enc(f"c{i}".encode(), uk), "secureNote": {"type": 0},
                                                    "favorite": False, "reprompt": 0, "notes": None, "organizationId": None, "encryptedFor": uid},
                           token=tok, base=base)["id"]
        with cf.ThreadPoolExecutor(8) as ex:
            made = set(ex.map(mk, range(20)))
        ids = {c["id"] for c in ft.http("GET", "/api/ciphers", token=tok, base=A)["data"]}
        assert made | {cid} <= ids, f"missing {len(made - ids)} concurrent writes"
        procs[0].terminate(); procs[0].wait(timeout=10)
        again = ft.http("GET", "/api/sync", token=tok, base=B)
        assert len(again["ciphers"]) == 21, len(again["ciphers"])
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
