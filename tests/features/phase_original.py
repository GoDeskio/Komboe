# Komboe-original vault features. Loaded into run.py. Talks to komboe.platform,
# which stores ciphertext only.
import tempfile
from komboe.platform.crypto import dec, dec_str, enc, enc_str, master_key, password_hash, stretch
from komboe.platform.localvault import LocalVault
from komboe.platform.routes.vault_extra import yubikey_key, yubikey_response

def plat():
    if "plat" not in S:
        from komboe.platform.server import serve_in_thread
        directory = tempfile.mkdtemp(prefix="korig-")
        httpd, db = serve_in_thread(os.path.join(directory, "orig.sqlite3"))
        S["plat"] = (f"http://127.0.0.1:{httpd.server_address[1]}", db, httpd)
    return S["plat"]

def puser():
    base, db, _httpd = plat()
    email = f"p-{uuid.uuid4().hex[:8]}@komboe.test"
    pw = "Komboe-P-" + uuid.uuid4().hex
    mk = master_key(pw, email)
    uk = os.urandom(64)
    http("POST", "/api/accounts/register", {
        "email": email, "masterPasswordHash": password_hash(mk, pw), "kdfIterations": 600000,
        "userSymmetricKey": enc(uk, stretch(mk)), "name": "P",
    }, base=base)
    tok = http("POST", "/identity/login", {"email": email, "masterPasswordHash": password_hash(mk, pw)}, base=base)
    assert tok["vaultKeyIncluded"] is False and "userKey" not in tok
    return {"email": email, "password": pw, "uk": uk, "token": tok["accessToken"], "base": base, "db": db}

def absent(db, *secrets):
    raw = open(db.path, "rb").read()
    for secret in secrets:
        blob = secret if isinstance(secret, bytes) else str(secret).encode()
        assert blob not in raw, secret

def sealed_item(u, item_type, fields, **extra):
    return http("POST", "/api/ciphers", {
        "type": item_type,
        "name": enc_str(fields.get("name") or fields.get("ssid") or "item", u["uk"]),
        "data": enc_str(json.dumps(fields), u["uk"]),
        **extra,
    }, token=u["token"], base=u["base"])

@t(4)
def _():
    u = puser(); label = "tag-" + uuid.uuid4().hex
    tag = http("POST", "/api/tags", {"name": enc_str(label, u["uk"])}, token=u["token"], base=u["base"])
    item = "tagged-" + uuid.uuid4().hex
    made = sealed_item(u, 1, {"name": item, "username": "u", "password": "p"}, tagIds=[tag["id"]])
    sync = http("GET", "/api/sync", token=u["token"], base=u["base"])
    got = next(t for t in sync["tags"] if t["id"] == tag["id"])
    assert dec_str(got["name"], u["uk"]) == label
    cipher = next(c for c in sync["ciphers"] if c["id"] == made["id"])
    assert tag["id"] in cipher["tagIds"]
    absent(u["db"], label, item)
    return DONE("encrypted tag created, linked to an item, decrypted on sync; tag name absent from the DB")

@t(15)
def _():
    u = puser(); token = uuid.uuid4().hex
    specs = {
        9: {"name": f"wifi-{token}", "ssid": f"ssid-{token}", "password": f"wifi-pw-{token}", "security": "WPA2", "hidden": False},
        8: {"name": f"pass-{token}", "fullName": f"Ada {token}", "number": f"PP-{token}", "country": "GB", "nationality": "GB", "expiry": "2030-01-01"},
        7: {"name": f"lic-{token}", "fullName": f"Ada {token}", "number": f"DL-{token}", "state": "CA", "expiry": "2031-06-01"},
        6: {"name": f"bank-{token}", "bankName": f"North {token}", "accountNumber": f"ACCT-{token}", "routingNumber": "021000021", "iban": f"IBAN-{token}", "swift": "NWBKGB2L"},
    }
    ids = {}
    for typ, fields in specs.items():
        ids[typ] = sealed_item(u, typ, fields)["id"]
    sync = http("GET", "/api/sync", token=u["token"], base=u["base"])
    for typ, fields in specs.items():
        row = next(c for c in sync["ciphers"] if c["id"] == ids[typ])
        assert row["type"] == typ
        opened = json.loads(dec_str(row["data"], u["uk"]))
        assert opened["name"] == fields["name"] and opened.get("password", opened.get("number", opened.get("accountNumber"))) 
        for value in fields.values():
            if isinstance(value, str) and len(value) > 8:
                assert value.encode() not in open(u["db"].path, "rb").read()
    return DONE("Wi-Fi, passport, license, and bank templates round-trip as encrypted item types 9/8/7/6")

@t(17)
def _():
    u = puser(); token = uuid.uuid4().hex
    fields = {"name": f"gpg-{token}", "publicKey": f"pub-{token}", "privateKey": f"priv-{token}", "fingerprint": f"fp-{token}", "userId": f"ada-{token}@komboe.test"}
    made = sealed_item(u, 10, fields)
    row = next(c for c in http("GET", "/api/sync", token=u["token"], base=u["base"])["ciphers"] if c["id"] == made["id"])
    opened = json.loads(dec_str(row["data"], u["uk"]))
    assert opened["privateKey"] == fields["privateKey"] and row["type"] == 10
    absent(u["db"], fields["privateKey"], fields["publicKey"])
    return DONE("GPG key item (type 10) stores an encrypted private key; plaintext key absent from the DB")

@t(18)
def _():
    u = puser(); token = uuid.uuid4().hex
    fields = {"name": f"bm-{token}", "url": f"https://example.test/{token}", "title": f"title-{token}"}
    made = sealed_item(u, 11, fields)
    row = next(c for c in http("GET", "/api/sync", token=u["token"], base=u["base"])["ciphers"] if c["id"] == made["id"])
    opened = json.loads(dec_str(row["data"], u["uk"]))
    assert opened["url"] == fields["url"] and row["type"] == 11
    absent(u["db"], fields["url"], fields["title"])
    return DONE("bookmark item (type 11) round-trips encrypted URL and title")

@t(37)
def _():
    u = puser(); other = puser(); secret = "expiry-secret-" + uuid.uuid4().hex
    org = http("POST", "/api/organizations", {"name": "Expiry Org"}, token=u["token"], base=u["base"])
    http("PUT", f"/api/organizations/{org['id']}/policies/password-expiry", {"enabled": True, "maxAgeDays": 30}, token=u["token"], base=u["base"])
    old = (datetime.now(timezone.utc) - timedelta(days=40)).isoformat()
    new = datetime.now(timezone.utc).isoformat()
    stale = sealed_item(u, 1, {"name": "stale", "password": secret}, organizationId=org["id"], passwordChangedAt=old)
    fresh = sealed_item(u, 1, {"name": "fresh", "password": secret}, organizationId=org["id"], passwordChangedAt=new)
    personal = sealed_item(u, 1, {"name": "personal", "password": secret}, passwordChangedAt=old)
    report = http("GET", f"/api/organizations/{org['id']}/reports/password-expiry", token=u["token"], base=u["base"])
    assert stale["id"] in report["expired"] and fresh["id"] not in report["expired"] and personal["id"] not in report["expired"]
    assert secret not in json.dumps(report)
    expect(404, http, "GET", f"/api/organizations/{org['id']}/reports/password-expiry", token=other["token"], base=u["base"])
    absent(u["db"], secret)
    return DONE("password-expiry policy lists org items older than maxAgeDays and hides personal items and passwords")

@t(53)
def _():
    u = puser(); secret = os.urandom(20); challenge = os.urandom(32)
    wrapped = enc(u["uk"], yubikey_key(yubikey_response(secret, challenge)))
    http("PUT", "/api/yubikey/unlock", {"challenge": b64(challenge), "wrappedUserKey": wrapped}, token=u["token"], base=u["base"])
    expect(400, http, "PUT", "/api/yubikey/unlock", {"challenge": b64(challenge), "wrappedUserKey": wrapped, "secret": b64(secret)}, token=u["token"], base=u["base"])
    blob = http("GET", "/api/yubikey/unlock", token=u["token"], base=u["base"])
    try:
        dec(blob["wrappedUserKey"], yubikey_key(yubikey_response(os.urandom(20), ub64(blob["challenge"]))))
        raise AssertionError("wrong YubiKey secret unwrapped the user key")
    except ValueError:
        pass
    opened = dec(blob["wrappedUserKey"], yubikey_key(yubikey_response(secret, ub64(blob["challenge"]))))
    assert opened == u["uk"]
    absent(u["db"], secret, u["uk"])
    return DONE("YubiKey HMAC-SHA1 challenge-response unwraps the user key client-side; secret and user key stay off the server")

@t(54)
def _():
    import subprocess
    u = puser(); home = tempfile.mkdtemp(prefix="kpgp-"); os.chmod(home, 0o700)
    env = dict(os.environ, GNUPGHOME=home); phrase = "pgp-pass-" + uuid.uuid4().hex
    subprocess.run(["gpg", "--batch", "--pinentry-mode", "loopback", "--passphrase", phrase, "--quick-gen-key", u["email"], "default", "default", "never"], env=env, check=True, capture_output=True)
    pub = subprocess.run(["gpg", "--armor", "--export", u["email"]], env=env, check=True, capture_output=True, text=True).stdout
    http("PUT", "/api/pgp/identity", {"publicKey": pub}, token=u["token"], base=u["base"])
    expect(400, http, "PUT", "/api/pgp/identity", {"publicKey": "-----BEGIN PGP PRIVATE KEY BLOCK-----\n\n-----END PGP PRIVATE KEY BLOCK-----"}, token=u["token"], base=u["base"])
    ch = http("POST", "/api/pgp/challenge", {"email": u["email"]}, base=u["base"])
    nonce = subprocess.run(["gpg", "--batch", "--pinentry-mode", "loopback", "--passphrase", phrase, "--decrypt"], input=ch["encryptedNonce"].encode(), env=env, check=True, capture_output=True).stdout
    sig = subprocess.run(["gpg", "--batch", "--pinentry-mode", "loopback", "--passphrase", phrase, "--detach-sign", "--armor"], input=nonce, env=env, check=True, capture_output=True).stdout.decode()
    mid = len(sig) // 2
    bad_sig = sig[:mid] + ("A" if sig[mid] != "A" else "B") + sig[mid + 1:]
    expect(401, http, "POST", "/api/pgp/verify", {"id": ch["id"], "signature": bad_sig}, base=u["base"])
    tok = http("POST", "/api/pgp/verify", {"id": ch["id"], "signature": sig}, base=u["base"])
    assert tok["authMethod"] == "pgp" and tok["vaultKeyIncluded"] is False and "userSymmetricKey" not in tok
    expect(401, http, "POST", "/api/pgp/verify", {"id": ch["id"], "signature": sig}, base=u["base"])
    assert http("GET", "/api/sync", token=tok["accessToken"], base=u["base"])["profile"]["email"] == u["email"]
    absent(u["db"], phrase)
    assert "PRIVATE KEY BLOCK" not in open(u["db"].path, "rb").read().decode(errors="replace")
    return DONE("PGP login: server encrypts a nonce to the public key, a passphrase-signed nonce issues an identity token, replay and private keys are refused")

@t(99)
def _():
    import subprocess
    u = puser(); home = tempfile.mkdtemp(prefix="kopgp-"); os.chmod(home, 0o700)
    env = dict(os.environ, GNUPGHOME=home)
    subprocess.run(["gpg", "--batch", "--pinentry-mode", "loopback", "--passphrase", "", "--quick-gen-key", u["email"], "default", "default", "never"], env=env, check=True, capture_output=True)
    pub = subprocess.run(["gpg", "--armor", "--export", u["email"]], env=env, check=True, capture_output=True, text=True).stdout
    secret = "openpgp-secret-" + uuid.uuid4().hex
    armored = subprocess.run(["gpg", "--batch", "--trust-model", "always", "--encrypt", "--armor", "--recipient", u["email"]], input=secret.encode(), env=env, check=True, capture_output=True).stdout.decode()
    made = http("POST", "/api/ciphers", {"type": 2, "name": armored, "data": armored}, token=u["token"], base=u["base"])
    row = next(c for c in http("GET", "/api/sync", token=u["token"], base=u["base"])["ciphers"] if c["id"] == made["id"])
    opened = subprocess.run(["gpg", "--batch", "--pinentry-mode", "loopback", "--passphrase", "", "--decrypt"], input=row["data"].encode(), env=env, check=True, capture_output=True).stdout.decode()
    assert opened == secret
    pub_only = tempfile.mkdtemp(prefix="kopgp-pub-"); os.chmod(pub_only, 0o700)
    penv = dict(os.environ, GNUPGHOME=pub_only)
    subprocess.run(["gpg", "--batch", "--import"], input=pub.encode(), env=penv, check=True, capture_output=True)
    refused = subprocess.run(["gpg", "--batch", "--decrypt"], input=row["data"].encode(), env=penv, capture_output=True)
    assert refused.returncode != 0
    absent(u["db"], secret)
    return DONE("OpenPGP message stored as the item payload; only the private key decrypts it, and the plaintext is absent from the DB")

@t(101)
def _():
    import socket
    directory = tempfile.mkdtemp(prefix="klocal-")
    path = os.path.join(directory, "vault.kdb")
    email, password, title, secret = "local@komboe.test", "local-master-password", "Local title " + uuid.uuid4().hex, "local-secret-" + uuid.uuid4().hex
    calls = []
    original = socket.socket
    def guard(*args, **kwargs):
        calls.append(args)
        raise AssertionError("local vault opened a socket")
    socket.socket = guard
    try:
        vault = LocalVault(path, email, password)
        vault.add_item(1, title, {"username": "ada", "password": secret})
        opened = vault.items()
        assert opened[0]["name"] == title and opened[0]["fields"]["password"] == secret
        vault.close()
        again = LocalVault(path, email, password)
        assert again.items()[0]["name"] == title and again.items()[0]["fields"]["password"] == secret
        again.close()
        try:
            LocalVault(path, email, "wrong-password")
            raise AssertionError("wrong password opened the local vault")
        except ValueError:
            pass
    finally:
        socket.socket = original
    assert calls == []
    raw = open(path, "rb").read()
    assert title.encode() not in raw and secret.encode() not in raw and password.encode() not in raw
    return DONE("local vault file encrypts items with the master password and performs no network I/O")
