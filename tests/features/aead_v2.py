#!/usr/bin/env python3
import base64
"""#100 Account encryption v2 (EncString type 7 / COSE Encrypt0 with an extended-nonce AEAD).

The server is algorithm-agnostic: it stores v2 key material and ciphertext as opaque blobs.
The algorithm is chosen by the Bitwarden SDK: XChaCha20-Poly1305 (COSE alg -70000) or
XAES-256-GCM (-70010; what sdk-internal in web-v2026.10.1 generates). The test reports which.

Runs against a server started with KOMBOE_AEAD_V2=true (default https://localhost:8543, its own DB).
  1. A new account registered in the real web vault takes the SDK v2 path: the server stores the
     signing keys + signed security state as opaque blobs, and the private key is type 7.
  2. Items that account creates (CLI, which uses the same SDK) are stored as type 7 ciphertext and decrypt.
  3. An existing v1 account (AES-CBC type 2 items) logs in to the web vault and is migrated client-side
     by key rotation: its rows become type 7, and the CLI still decrypts the old item.
  4. Downgrade guard: a v1 rotation or lower securityVersion on a v2 account is refused.
  5. Backward compatibility: the flag-off server (KOMBOE_URL_V1, default https://localhost:8443)
     refuses v2 key material and does not advertise the v2 flags; v1 clients are untouched.
Zero-knowledge: the DB is checked for every plaintext used here.
"""
import importlib.util, json, os, sqlite3, subprocess, sys, tempfile, uuid

V2 = os.environ.get("KOMBOE_AEAD_URL", "https://localhost:8543")
V1 = os.environ.get("KOMBOE_URL_V1", "https://localhost:8443")
DB = os.environ.get("KOMBOE_AEAD_DB", "/workspace/run/aead/data/db.sqlite3")
os.environ["KOMBOE_URL"] = V2
HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("ft", os.path.join(HERE, "run.py")); ft = importlib.util.module_from_spec(spec); spec.loader.exec_module(ft)
CLI = ["node", os.path.join(HERE, "../../clients/upstream/apps/cli/build/bw.js")]
SECRETS = []


def db(q, *a):
    c = sqlite3.connect(DB); r = c.execute(q, a).fetchall(); c.close(); return r


def cli_for(email, pw):
    home = tempfile.mkdtemp()
    env = dict(os.environ, XDG_CONFIG_HOME=home, BITWARDENCLI_APPDATA_DIR=home, KPW=pw,
               NODE_EXTRA_CA_CERTS=os.environ.get("NODE_EXTRA_CA_CERTS", "/workspace/run/tls/cert.pem"))
    run = lambda *a, inp=None: subprocess.run([*CLI, *a], capture_output=True, text=True, timeout=180, env=env, input=inp)
    run("config", "server", V2)
    r = run("login", email, "--passwordenv", "KPW", "--raw")
    assert r.returncode == 0, (r.stdout[-400:], r.stderr[-400:])
    return run, r.stdout.strip().splitlines()[-1]


def cli_item(run, sess, name, secret):
    tmpl = {"type": 1, "name": name, "notes": None, "favorite": False, "fields": [], "reprompt": 0,
            "login": {"username": "aead-user", "password": secret, "uris": []}, "secureNote": None, "card": None, "identity": None}
    import base64
    enc = base64.b64encode(json.dumps(tmpl).encode()).decode()
    r = run("create", "item", enc, "--session", sess)
    assert r.returncode == 0, (r.stdout[-400:], r.stderr[-400:])
    return json.loads(r.stdout)["id"]


def cli_password(run, sess, iid):
    run("sync", "--session", sess)
    r = run("get", "password", iid, "--session", sess)
    assert r.returncode == 0, (r.stdout[-400:], r.stderr[-400:]); return r.stdout.strip()


def cose_alg(enc):
    """Name the AEAD in a type-7 EncString's COSE protected header (alg label 1)."""
    raw = base64.b64decode(enc[2:] + "==")
    for code, name in ((b"\x01\x3a\x00\x01\x11\x6f", "XChaCha20-Poly1305"), (b"\x01\x3a\x00\x01\x11\x79", "XAES-256-GCM")):
        if code in raw[:40]:
            return name
    raise AssertionError("unknown COSE alg in type-7 EncString")


def user_row(email):
    return db("SELECT uuid, private_key, akey FROM users WHERE email = ?", email)[0]


def web_login(page, email, pw):
    page.goto(V2 + "/#/login", wait_until="domcontentloaded")
    page.fill("#email", email)
    cont = page.get_by_role("button", name="Continue")
    if cont.count():
        cont.click()
    page.fill("#masterPassword", pw)
    page.get_by_role("button", name="Log in", exact=True).click()


def wait_vault(page):
    page.wait_for_function("() => /vault|setup-extension/.test(location.hash)", timeout=90000)


def main():
    from playwright.sync_api import sync_playwright
    cfg = ft.http("GET", "/api/config", base=V2)
    assert cfg["featureStates"].get("pm-27278-v2-password-registration") and cfg["featureStates"].get("force-upgrade-v2-encryption"), cfg["featureStates"]
    cfg1 = ft.http("GET", "/api/config", base=V1)
    assert not cfg1["featureStates"].get("pm-27278-v2-password-registration") and not cfg1["featureStates"].get("force-upgrade-v2-encryption")
    print("  flags: advertised only on the KOMBOE_AEAD_V2 server")

    # v1 account created before the upgrade, with a v1 (type 2) item
    old = ft.User(); old_secret = "aead-v1-secret-" + uuid.uuid4().hex[:6]; SECRETS.append(old_secret)
    old_id = old.api("POST", "/api/ciphers", old.cipher({"login": {"username": old.e("u"), "password": old.e(old_secret), "uris": []}}))["id"]
    assert db("SELECT data FROM ciphers WHERE uuid=?", old_id)[0][0].count('"2.') >= 1
    assert not db("SELECT 1 FROM komboe_account_keys_v2 WHERE user_uuid=?", old.id)

    email = f"aead-{uuid.uuid4().hex[:8]}@komboe.test"; pw = "Komboe-AEAD-" + uuid.uuid4().hex
    tok = ft.http("POST", "/identity/accounts/register/send-verification-email", {"email": email, "name": "AEAD"}, base=V2)
    assert tok, "test server must run without SMTP so the verify token is returned"
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        ctx = browser.new_context(ignore_https_errors=True, viewport={"width": 1400, "height": 900})
        page = ctx.new_page(); page.set_default_timeout(30000)
        import urllib.parse
        page.goto(V2 + "/#/finish-signup?" + urllib.parse.urlencode({"email": email, "token": tok}), wait_until="domcontentloaded")
        page.fill("#input-password-form_new-password", pw)
        page.fill("#input-password-form_new-password-confirm", pw)
        chk = page.locator("#input-password-form_check-for-breaches")
        if chk.count() and chk.is_checked():
            chk.uncheck()
        page.get_by_role("button", name="Create account").click()
        try:
            page.wait_for_function("() => !location.hash.includes('finish-signup')", timeout=90000)
        except Exception:
            page.screenshot(path="/tmp/aead-reg.png"); raise
        page.wait_for_timeout(2000)
        uid, priv, akey = user_row(email)
        row = db("SELECT wrapped_signing_key, verifying_key, signed_public_key, security_state, security_version FROM komboe_account_keys_v2 WHERE user_uuid=?", uid)
        assert row, "web registration did not send v2 keys"
        wsk, vk, spk, st, ver = row[0]
        assert wsk.startswith("7.") and priv.startswith("7.") and spk and st and ver >= 2, (wsk[:4], priv[:4], ver)
        print(f"  web registration: v2 account (private key + signing key are type 7 / {cose_alg(priv)}, securityVersion {ver})")

        run, sess = cli_for(email, pw)
        new_secret = "aead-v2-secret-" + uuid.uuid4().hex[:6]; SECRETS.append(new_secret)
        nid = cli_item(run, sess, "aead-v2-item", new_secret)
        data, ckey, cname = db("SELECT data, key, name FROM ciphers WHERE uuid=?", nid)[0]
        # SDK v2 cipher: per-cipher key wrapped under the v2 user key (type 7),
        # contents in an opaque COSE Encrypt0 data envelope the server stores verbatim.
        blob = json.loads(json.loads(data)["komboeBlob"])
        assert ckey.startswith("7.") and cname == "" and set(blob) >= {"envelope", "wrapped_cek"}, (ckey[:4], sorted(blob))
        assert base64.b64decode(blob["envelope"] + "==")[:1] == b"\x83", "envelope is not COSE Encrypt0"
        assert cli_password(run, sess, nid) == new_secret
        print(f"  new v2 item: cipher key type 7 ({cose_alg(ckey)}), contents in opaque COSE envelope, decrypts in the CLI")

        # v1 -> v2 migration on web unlock
        page2 = ctx.browser.new_context(ignore_https_errors=True, viewport={"width": 1400, "height": 900}).new_page(); page2.set_default_timeout(30000)
        web_login(page2, old.email, old.pw)
        try:
            page2.get_by_text("Add it later").click(timeout=15000)
        except Exception:
            pass
        try:
            wait_vault(page2)
        except Exception:
            page2.screenshot(path="/tmp/aead-mig.png"); raise
        for _ in range(60):
            if db("SELECT 1 FROM komboe_account_keys_v2 WHERE user_uuid=?", old.id):
                break
            page2.wait_for_timeout(1000)
        else:
            page2.screenshot(path="/tmp/aead-mig.png"); raise AssertionError("v1 account was not upgraded on web login")
        page2.wait_for_timeout(1500)
        _, opriv, _ = user_row(old.email)
        odata, okey, oname = db("SELECT data, key, name FROM ciphers WHERE uuid=?", old_id)[0]
        oblob = json.loads(json.loads(odata)["komboeBlob"])
        assert opriv.startswith("7.") and okey.startswith("7.") and oname == "" and set(oblob) >= {"envelope", "wrapped_cek"}, (opriv[:4], (okey or "")[:4], sorted(oblob))
        run_o, sess_o = cli_for(old.email, old.pw)
        assert cli_password(run_o, sess_o, old_id) == old_secret
        print("  v1 account upgraded on web unlock: keys re-wrapped to type 7, old item moved into a COSE envelope and still decrypts")
        browser.close()

    # Downgrade guard (raw API, as an attacker-controlled client would)
    old.login()
    keys = old.api("GET", "/api/accounts/keys")
    ak = keys["accountKeys"]; assert ak["signatureKeyPair"] and ak["securityState"]["securityVersion"] >= 2
    base = {"oldMasterKeyAuthenticationHash": old.hash,
            "accountUnlockData": {"emergencyAccessUnlockData": [], "organizationAccountRecoveryUnlockData": [],
                                  "masterPasswordUnlockData": {"kdfType": 0, "kdfIterations": old.it, "kdfParallelism": None, "kdfMemory": None,
                                                               "email": old.email, "masterKeyAuthenticationHash": old.hash, "masterKeyEncryptedUserKey": keys["key"]}},
            "accountData": {"ciphers": [], "folders": [], "sends": []}}
    v1keys = {"userKeyEncryptedAccountPrivateKey": keys["privateKey"], "accountPublicKey": keys["publicKey"]}
    for label, ak_req, want in [
        ("v1 rotation", v1keys, "downgrade"),
        ("lower securityVersion", dict(v1keys, publicKeyEncryptionKeyPair={"wrappedPrivateKey": keys["privateKey"], "publicKey": keys["publicKey"], "signedPublicKey": ak["publicKeyEncryptionKeyPair"]["signedPublicKey"]},
                                       signatureKeyPair={"wrappedSigningKey": ak["signatureKeyPair"]["wrappedSigningKey"], "verifyingKey": ak["signatureKeyPair"]["verifyingKey"]},
                                       securityState={"securityState": ak["securityState"]["securityState"], "securityVersion": 1}), "securityVersion"),
    ]:
        try:
            old.api("POST", "/api/accounts/key-management/rotate-user-account-keys", dict(base, accountKeys=ak_req)); raise AssertionError(label + " accepted")
        except ft.HTTPErr as e:
            assert want.lower() in str(e).lower(), (label, str(e)[:300])
    assert user_row(old.email)[1] == keys["privateKey"], "refused rotation must not change anything"
    print("  downgrade guard: v1 rotation and lower securityVersion refused, nothing written")

    # Flag-off server refuses v2 key material at registration
    e1 = f"aead-off-{uuid.uuid4().hex[:6]}@komboe.test"
    tok1 = ft.http("POST", "/identity/accounts/register/send-verification-email", {"email": e1, "name": "x"}, base=V1)
    if tok1:
        try:
            ft.http("POST", "/identity/accounts/register/finish", {"email": e1, "emailVerificationToken": tok1, "masterPasswordHash": "aGFzaA==", "kdf": 0, "kdfIterations": 600000,
                    "userSymmetricKey": "2.a|b|c", "accountKeys": {"publicKeyEncryptionKeyPair": {"wrappedPrivateKey": "7.x", "publicKey": "cA==", "signedPublicKey": "cw=="},
                    "signatureKeyPair": {"wrappedSigningKey": "7.y", "verifyingKey": "dg=="}, "securityState": {"securityState": "cw==", "securityVersion": 2}}}, base=V1)
            raise AssertionError("flag-off server accepted v2 keys")
        except ft.HTTPErr as e:
            assert "KOMBOE_AEAD_V2" in str(e), str(e)[:300]
        print("  flag-off server: v2 key material refused, v1 path unchanged")
    else:
        print("  flag-off server: SMTP on, v2 refusal checked by the server unit path only")

    dump = b"".join(open(f, "rb").read() for f in (DB, DB + "-wal") if os.path.exists(f))
    for s in SECRETS + [pw, old.pw]:
        assert s.encode() not in dump, "plaintext in DB"
    print("  DB: ciphertext only")
    print("AEAD V2 PASS")


if __name__ == "__main__":
    main()
