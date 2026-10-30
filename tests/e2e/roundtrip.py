#!/usr/bin/env python3
"""Komboe zero-knowledge round-trip test.

Registers a fresh account, logs in, creates an encrypted login item, syncs it
back, decrypts it client-side, then opens the server's SQLite DB and proves
that no plaintext secret (master password, item name, username, password, note,
or the raw user/item keys) is stored anywhere in it.

All crypto happens here, in the client, using the Bitwarden-compatible scheme
(PBKDF2-SHA256 master key -> HKDF stretched enc/mac keys -> AES-256-CBC +
HMAC-SHA256 "type 2" EncStrings; RSA-2048 OAEP keypair). The server only ever
receives ciphertext plus a one-way master-password *hash*.

Usage: KOMBOE_URL=http://127.0.0.1:8000 KOMBOE_DB=/path/db.sqlite3 python3 roundtrip.py
"""
import base64, hashlib, hmac, json, os, sqlite3, sys, uuid, urllib.request, urllib.parse
from cryptography.hazmat.primitives import hashes, padding, serialization
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.asymmetric import rsa, padding as apad
from cryptography.hazmat.primitives.kdf.hkdf import HKDFExpand

URL = os.environ.get("KOMBOE_URL", "http://127.0.0.1:8000").rstrip("/")
DB = os.environ.get("KOMBOE_DB")
ITER = 600_000
b64 = lambda b: base64.b64encode(b).decode()
ub64 = base64.b64decode

def http(method, path, body=None, form=None, token=None, accept_json=True):
    headers = {"Device-Type": "10", "Bitwarden-Client-Name": "cli", "Bitwarden-Client-Version": "2026.10.1"}
    data = None
    if form is not None:
        data = urllib.parse.urlencode(form).encode(); headers["Content-Type"] = "application/x-www-form-urlencoded"
    elif body is not None:
        data = json.dumps(body).encode(); headers["Content-Type"] = "application/json"
    if accept_json: headers["Accept"] = "application/json"
    if token: headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(URL + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req) as r:
            raw = r.read(); return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        sys.exit(f"{method} {path} -> {e.code}: {e.read()[:400]!r}")

def stretch(key):  # HKDF-Expand(SHA256) -> enc||mac
    f = lambda info: HKDFExpand(hashes.SHA256(), 32, info).derive(key)
    return f(b"enc") + f(b"mac")

def enc(plain: bytes, key64: bytes) -> str:
    ek, mk, iv = key64[:32], key64[32:], os.urandom(16)
    p = padding.PKCS7(128).padder(); data = p.update(plain) + p.finalize()
    e = Cipher(algorithms.AES(ek), modes.CBC(iv)).encryptor(); ct = e.update(data) + e.finalize()
    mac = hmac.new(mk, iv + ct, hashlib.sha256).digest()
    return f"2.{b64(iv)}|{b64(ct)}|{b64(mac)}"

def dec(s: str, key64: bytes) -> bytes:
    t, rest = s.split(".", 1); assert t == "2", t
    iv, ct, mac = map(ub64, rest.split("|"))
    assert hmac.compare_digest(mac, hmac.new(key64[32:], iv + ct, hashlib.sha256).digest()), "MAC mismatch"
    d = Cipher(algorithms.AES(key64[:32]), modes.CBC(iv)).decryptor(); data = d.update(ct) + d.finalize()
    u = padding.PKCS7(128).unpadder(); return u.update(data) + u.finalize()

def main():
    email = f"rt-{uuid.uuid4().hex[:10]}@komboe.test"
    master_pw = "Komboe-RT-" + uuid.uuid4().hex
    secret = {"name": "RT-NAME-" + uuid.uuid4().hex, "username": "RT-USER-" + uuid.uuid4().hex,
              "password": "RT-PASS-" + uuid.uuid4().hex, "notes": "RT-NOTE-" + uuid.uuid4().hex}

    master_key = hashlib.pbkdf2_hmac("sha256", master_pw.encode(), email.encode(), ITER, 32)
    pw_hash = b64(hashlib.pbkdf2_hmac("sha256", master_key, master_pw.encode(), 1, 32))
    user_key = os.urandom(64)                       # never leaves the client unencrypted
    protected_key = enc(user_key, stretch(master_key))
    priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pub_der = priv.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    priv_der = priv.private_bytes(serialization.Encoding.DER, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())

    # 1. register (verification-token flow; SIGNUPS_VERIFY off locally)
    tok = http("POST", "/identity/accounts/register/send-verification-email", {"email": email, "name": "RT"})
    http("POST", "/identity/accounts/register/finish", {
        "email": email, "emailVerificationToken": tok, "masterPasswordHash": pw_hash, "masterPasswordHint": None,
        "userSymmetricKey": protected_key, "kdf": 0, "kdfIterations": ITER,
        "userAsymmetricKeys": {"publicKey": b64(pub_der), "encryptedPrivateKey": enc(priv_der, user_key)}})
    print("register OK", email)

    # 2. prelogin + login
    pre = http("POST", "/identity/accounts/prelogin", {"email": email})
    assert pre["kdf"] == 0 and pre["kdfIterations"] == ITER, pre
    login = http("POST", "/identity/connect/token", form={
        "grant_type": "password", "username": email, "password": pw_hash, "scope": "api offline_access",
        "client_id": "cli", "deviceType": "8", "deviceIdentifier": str(uuid.uuid4()), "deviceName": "komboe-rt"})
    at = login["access_token"]
    uk = dec(login["Key"], stretch(master_key)); assert uk == user_key
    seg = at.split(".")[1]; uid = json.loads(base64.urlsafe_b64decode(seg + "=" * (-len(seg) % 4)))["sub"]
    print("login OK; user key unwrapped client-side")

    # 3. create item (all fields encrypted with the user key)
    cipher = http("POST", "/api/ciphers", {"type": 1, "encryptedFor": uid, "name": enc(secret["name"].encode(), uk),
        "notes": enc(secret["notes"].encode(), uk), "favorite": False, "reprompt": 0,
        "login": {"username": enc(secret["username"].encode(), uk), "password": enc(secret["password"].encode(), uk), "uris": []}}, token=at)
    print("create item OK", cipher["id"])

    # 4. sync + decrypt
    sync = http("GET", "/api/sync?excludeDomains=true", token=at)
    c = next(x for x in sync["ciphers"] if x["id"] == cipher["id"])
    got = {"name": dec(c["name"], uk).decode(), "notes": dec(c["notes"], uk).decode(),
           "username": dec(c["login"]["username"], uk).decode(), "password": dec(c["login"]["password"], uk).decode()}
    assert got == secret, (got, secret)
    print("sync + client-side decrypt OK")

    # 5. server DB holds only ciphertext
    if DB:
        con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        blob = b""
        for (t,) in con.execute("select name from sqlite_master where type='table'"):
            for row in con.execute(f'select * from "{t}"'):
                blob += b"\x00".join(str(v).encode() if not isinstance(v, bytes) else v for v in row)
        needles = {"master password": master_pw.encode(), "user key(b64)": b64(user_key).encode(), "user key(raw)": user_key,
                   "master key(b64)": b64(master_key).encode(), "private key(b64)": b64(priv_der).encode(),
                   **{k: v.encode() for k, v in secret.items()}}
        leaks = [k for k, v in needles.items() if v in blob]
        assert not leaks, f"PLAINTEXT LEAK in server DB: {leaks}"
        assert protected_key.encode() in blob and c["login"]["password"].encode() in blob  # ciphertext is there
        print(f"server DB check OK: {len(needles)} plaintext secrets absent, ciphertext present")
    print("ROUNDTRIP PASS")

if __name__ == "__main__":
    main()
