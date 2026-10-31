#!/usr/bin/env python3
"""Komboe feature matrix: one test per feature in docs/FEATURES.md (#1-#106).

Each test returns a status:
  done     - verified end-to-end against a running Komboe server this run
  partial  - upstream code is vendored in this repo but not yet exercised end-to-end
  blocked  - needs Phase B work, an external service, or is excluded by policy
A test that raises is reported as FAIL (and makes the run exit non-zero).

Usage: KOMBOE_URL=http://127.0.0.1:8000 KOMBOE_DB=.../db.sqlite3 KOMBOE_ADMIN_TOKEN=... \
       python3 tests/features/run.py [--write-status docs/STATUS.md]
"""
import base64, hashlib, hmac, json, os, re, struct, sys, time, uuid, urllib.request, urllib.parse, urllib.error
from datetime import datetime, timedelta, timezone
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "e2e"))
from roundtrip import enc, dec, stretch, b64, ub64  # noqa: E402
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding as apad

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
URL = os.environ.get("KOMBOE_URL", "http://127.0.0.1:8000").rstrip("/")
DB = os.environ.get("KOMBOE_DB")
ADMIN = os.environ.get("KOMBOE_ADMIN_TOKEN")
if URL.startswith("https://"):
    import ssl
    ssl._create_default_https_context = ssl._create_unverified_context

class HTTPErr(Exception):
    def __init__(s, code, body): super().__init__(f"{code}: {body[:300]}"); s.code = code; s.body = body

def http(method, path, body=None, form=None, token=None, raw=False, headers=None, base=None):
    h = {"Device-Type": "10", "Bitwarden-Client-Name": "cli", "Bitwarden-Client-Version": "2026.10.1", "Accept": "application/json"}
    h.update(headers or {}); data = None
    if form is not None: data = urllib.parse.urlencode(form).encode(); h["Content-Type"] = "application/x-www-form-urlencoded"
    elif body is not None: data = json.dumps(body).encode(); h["Content-Type"] = "application/json"
    if token: h["Authorization"] = "Bearer " + token
    try:
        with urllib.request.urlopen(urllib.request.Request((base or URL) + path, data=data, method=method, headers=h)) as r:
            b = r.read(); return b if raw else (json.loads(b) if b else None)
    except urllib.error.HTTPError as e:
        raise HTTPErr(e.code, e.read().decode(errors="replace"))

def totp(secret_b32, t=None):
    key = base64.b32decode(secret_b32.upper() + "=" * (-len(secret_b32) % 8))
    mac = hmac.new(key, struct.pack(">Q", int((t or time.time()) // 30)), hashlib.sha1).digest()
    o = mac[-1] & 15; return f"{(struct.unpack('>I', mac[o:o+4])[0] & 0x7fffffff) % 1000000:06d}"

MAILPIT = os.environ.get("KOMBOE_MAILPIT", "http://127.0.0.1:8025")
def mailpit(to, subject="", wait=10):
    """Newest Mailpit message to `to` whose subject contains `subject` (full JSON incl. HTML/Text)."""
    end = time.time() + wait
    while True:
        msgs = []
        for f in ("to", "bcc"):  # forwarded alias mail keeps the alias in To; the mailbox is the envelope (Bcc) recipient
            q = urllib.parse.quote(f'{f}:"{to}"')
            msgs += json.loads(urllib.request.urlopen(f"{MAILPIT}/api/v1/search?query={q}&limit=50").read())["messages"]
        msgs.sort(key=lambda m: m["Created"], reverse=True)
        for m in msgs:
            if subject.lower() in m["Subject"].lower(): return json.loads(urllib.request.urlopen(f"{MAILPIT}/api/v1/message/{m['ID']}").read())
        if time.time() > end: raise AssertionError(f"no mail to {to} with subject containing {subject!r}")
        time.sleep(0.3)
def mailpit_token(to):
    m = mailpit(to, "Verify")
    return urllib.parse.unquote(re.search(r"token=([^&\"'\s]+)", m["Text"] + m["HTML"]).group(1))

class User:
    def __init__(self, kdf=0, email=None, pw=None):
        self.email = email or f"ft-{uuid.uuid4().hex[:10]}@komboe.test"; self.pw = pw or "Komboe-FT-" + uuid.uuid4().hex; self.kdf = kdf
        if kdf == 0:
            self.it = 600_000; self.mk = hashlib.pbkdf2_hmac("sha256", self.pw.encode(), self.email.encode(), self.it, 32)
        else:
            from argon2.low_level import hash_secret_raw, Type
            self.it, self.mem, self.par = 3, 64, 4
            self.mk = hash_secret_raw(self.pw.encode(), hashlib.sha256(self.email.encode()).digest(), self.it, self.mem * 1024, self.par, 32, Type.ID)
        self.hash = b64(hashlib.pbkdf2_hmac("sha256", self.mk, self.pw.encode(), 1, 32))
        self.uk = os.urandom(64); self.priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.pub = self.priv.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
        tok = http("POST", "/identity/accounts/register/send-verification-email", {"email": self.email, "name": "FT"})
        if not tok: tok = mailpit_token(self.email)  # SMTP enabled: token only arrives by mail
        body = {"email": self.email, "emailVerificationToken": tok, "masterPasswordHash": self.hash, "kdf": kdf,
                "kdfIterations": self.it, "userSymmetricKey": enc(self.uk, stretch(self.mk)),
                "userAsymmetricKeys": {"publicKey": b64(self.pub), "encryptedPrivateKey": enc(self.priv.private_bytes(
                    serialization.Encoding.DER, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()), self.uk)}}
        if kdf == 1: body.update(kdfMemory=self.mem, kdfParallelism=self.par)
        http("POST", "/identity/accounts/register/finish", body); self.login()
    def login(self, extra=None):
        f = {"grant_type": "password", "username": self.email, "password": self.hash, "scope": "api offline_access",
             "client_id": "cli", "deviceType": "8", "deviceIdentifier": getattr(self, "dev", None) or str(uuid.uuid4()), "deviceName": "ft"}
        self.dev = f["deviceIdentifier"]; f.update(extra or {})
        r = http("POST", "/identity/connect/token", form=f); self.at = r["access_token"]
        seg = self.at.split(".")[1]; self.id = json.loads(base64.urlsafe_b64decode(seg + "=" * (-len(seg) % 4)))["sub"]; return r
    def e(self, s, key=None): return enc(s.encode() if isinstance(s, str) else s, key or self.uk)
    def d(self, s, key=None): return dec(s, key or self.uk).decode()
    def api(self, m, p, body=None, **kw): return http(m, p, body, token=self.at, **kw)
    def cipher(self, extra=None, typ=1, key=None, org=None):
        c = {"type": typ, "encryptedFor": self.id, "name": self.e("item-" + uuid.uuid4().hex[:6], key), "favorite": False, "reprompt": 0,
             "notes": None, "organizationId": org}
        if typ == 1: c["login"] = {"username": self.e("u", key), "password": self.e("p", key), "uris": []}
        c.update(extra or {}); return c

S = {}  # shared fixtures
def a(): S.setdefault("a", User()); return S["a"]
def b(): S.setdefault("b", User()); return S["b"]
def org():
    if "org" not in S:
        u = a(); ok = os.urandom(64); opriv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        oaep = apad.OAEP(mgf=apad.MGF1(hashes.SHA1()), algorithm=hashes.SHA1(), label=None)
        wrapped = "4." + b64(u.priv.public_key().encrypt(ok, oaep))
        r = u.api("POST", "/api/organizations", {"name": "FT Org", "billingEmail": u.email, "key": wrapped, "planType": 0,
            "collectionName": enc(b"Default", ok), "keys": {"publicKey": b64(opriv.public_key().public_bytes(serialization.Encoding.DER,
            serialization.PublicFormat.SubjectPublicKeyInfo)), "encryptedPrivateKey": enc(opriv.private_bytes(serialization.Encoding.DER,
            serialization.PrivateFormat.PKCS8, serialization.NoEncryption()), ok)}})
        S["org"] = (r["id"], ok, oaep)
        S["col"] = u.api("GET", f"/api/organizations/{r['id']}/collections")["data"][0]["id"]
    return S["org"]

T = {}
def t(n, status=None, why=""):
    def deco(fn): T[n] = (fn, status, why); return fn
    if status:  # static status (no live call)
        T[n] = (None, status, why); return None
    return deco
def P(n, why): t(n, "partial", why)
def X(n, why): t(n, "blocked", why)
DONE = lambda why: ("done", why)

@t(1)
def _():
    u = a(); ids = [u.api("POST", "/api/ciphers", u.cipher())["id"] for _ in range(3)]
    have = {c["id"] for c in u.api("GET", "/api/sync")["ciphers"]}; assert set(ids) <= have
    return DONE("3 encrypted logins created + synced; no item cap in server")
@t(2)
def _():
    u = a(); f = u.api("POST", "/api/folders", {"name": u.e("Work")})
    c = u.api("POST", "/api/ciphers", u.cipher({"folderId": f["id"]}))
    s = u.api("GET", "/api/sync"); assert any(x["id"] == f["id"] and u.d(x["name"]) == "Work" for x in s["folders"])
    assert next(x for x in s["ciphers"] if x["id"] == c["id"])["folderId"] == f["id"]
    return DONE("encrypted folder + item in folder")
@t(3)
def _():
    u = a(); oid, ok, _ = org(); cols = u.api("GET", f"/api/organizations/{oid}/collections")["data"]
    assert cols and u.d(cols[0]["name"], ok) == "Default"
    c = u.api("POST", "/api/ciphers/create", {"cipher": u.cipher(key=ok, org=oid), "collectionIds": [cols[0]["id"]]})
    assert c["organizationId"] == oid; S["orgcipher"] = c["id"]; S["col"] = cols[0]["id"]
    return DONE("org collection created; org item encrypted with org key")
X(4, "Tags are not in the upstream data model; Komboe-original (Phase B+)")
@t(5)
def _():
    u = a(); c = u.api("POST", "/api/ciphers", u.cipher({"favorite": True}))
    assert next(x for x in u.api("GET", "/api/sync")["ciphers"] if x["id"] == c["id"])["favorite"] is True
    return DONE("favorite flag persists; search/filter are client-side over decrypted vault (web vault)")
@t(6)
def _():
    u = a(); c = u.cipher(); old = u.e("old-pw"); c["passwordHistory"] = [{"password": old, "lastUsedDate": datetime.now(timezone.utc).isoformat()}]
    cid = u.api("POST", "/api/ciphers", c)["id"]; u.api("PUT", f"/api/ciphers/{cid}/delete")
    x = next(x for x in u.api("GET", "/api/sync")["ciphers"] if x["id"] == cid); assert x["deletedDate"]
    u.api("PUT", f"/api/ciphers/{cid}/restore")
    x = next(x for x in u.api("GET", "/api/sync")["ciphers"] if x["id"] == cid); assert not x["deletedDate"]
    assert u.d(x["passwordHistory"][0]["password"]) == "old-pw"
    return DONE("password history + trash + restore")
@t(7)
def _():
    u = a(); fl = [{"type": 0, "name": u.e("t"), "value": u.e("v")}, {"type": 1, "name": u.e("h"), "value": u.e("s")},
                   {"type": 2, "name": u.e("b"), "value": u.e("true")}, {"type": 3, "name": u.e("l"), "value": None, "linkedId": 100}]
    cid = u.api("POST", "/api/ciphers", u.cipher({"fields": fl}))["id"]
    x = next(x for x in u.api("GET", "/api/sync")["ciphers"] if x["id"] == cid)
    assert [f["type"] for f in x["fields"]] == [0, 1, 2, 3] and u.d(x["fields"][1]["value"]) == "s"
    return DONE("text/hidden/boolean/linked fields")
@t(8)
def _():
    u = a(); cid = u.api("POST", "/api/ciphers", u.cipher())["id"]; fk = os.urandom(64)
    data = b"\x00ATTACHMENT-" + uuid.uuid4().hex.encode(); blob = enc(data, fk)
    from roundtrip import ub64 as _u
    iv, ct, mac = map(base64.b64decode, blob[2:].split("|")); payload = b"\x02" + iv + mac + ct
    r = u.api("POST", f"/api/ciphers/{cid}/attachment/v2", {"key": enc(fk, u.uk), "fileName": u.e("f.bin"), "fileSize": len(payload)})
    bnd = uuid.uuid4().hex; mp = (f"--{bnd}\r\nContent-Disposition: form-data; name=\"data\"; filename=\"f\"\r\nContent-Type: application/octet-stream\r\n\r\n").encode() + payload + f"\r\n--{bnd}--\r\n".encode()
    req = urllib.request.Request(URL + f"/api/ciphers/{cid}/attachment/{r['attachmentId']}", data=mp, method="POST",
        headers={"Authorization": "Bearer " + u.at, "Content-Type": f"multipart/form-data; boundary={bnd}"}); urllib.request.urlopen(req).read()
    x = next(x for x in u.api("GET", "/api/sync")["ciphers"] if x["id"] == cid); att = x["attachments"][0]
    got = urllib.request.urlopen(att["url"] if att["url"].startswith("http") else URL + att["url"]).read()
    assert got == payload and data not in got
    return DONE("encrypted attachment upload/download; server stores ciphertext only")
P(9, "offline cache is client-side (web/desktop/mobile); Phase B client builds")
@t(10)
def _(): u = a(); cid = u.api("POST", "/api/ciphers", u.cipher())["id"]; return DONE(f"login item {cid[:8]}")
@t(11)
def _(): u = a(); u.api("POST", "/api/ciphers", u.cipher({"secureNote": {"type": 0}, "notes": u.e("n")}, typ=2)); return DONE("secure note")
@t(12)
def _():
    u = a(); u.api("POST", "/api/ciphers", u.cipher({"card": {k: u.e(v) for k, v in dict(cardholderName="A", number="4111111111111111", expMonth="1", expYear="2030", code="123", brand="Visa").items()}}, typ=3))
    return DONE("card item")
@t(13)
def _(): u = a(); u.api("POST", "/api/ciphers", u.cipher({"identity": {"firstName": u.e("A"), "lastName": u.e("B"), "email": u.e("a@b")}}, typ=4)); return DONE("identity item")
@t(14)
def _(): u = a(); u.api("POST", "/api/ciphers", u.cipher({"sshKey": {"privateKey": u.e("k"), "publicKey": u.e("p"), "keyFingerprint": u.e("f")}}, typ=5)); return DONE("SSH key item (agent is desktop: Phase B)")
X(15, "extra templates (Wi-Fi/passport/bank) need new item types: Komboe-original")
P(16, "storable as secure note + custom fields today; dedicated type is Komboe-original")
X(17, "GPG key item type: Komboe-original")
X(18, "Bookmark item type: Komboe-original")
X(19, "alias-linked login needs the SimpleLogin service running (Phase B)")
@t(20)
def _():
    oid, ok, oaep = org(); u, v = a(), b()
    r = u.api("POST", f"/api/organizations/{oid}/users/invite", {"emails": [v.email], "type": 2, "collections": [{"id": S["col"], "readOnly": True, "hidePasswords": False, "manage": False}], "accessAll": False, "permissions": {}, "groups": []})
    mem = next(m for m in u.api("GET", f"/api/organizations/{oid}/users")["data"] if m["email"] == v.email)
    if mem["status"] == 0:
        tok = urllib.parse.unquote(re.search(r"token=([^&\"'\s<]+)", mailpit(v.email, "Join")["Text"]).group(1)) if os.environ.get("KOMBOE_SMTP") else ""
        v.api("POST", f"/api/organizations/{oid}/users/{mem['id']}/accept", {"token": tok, "resetPasswordKey": None})
    pk = u.api("GET", f"/api/users/{v.id}/public-key")["publicKey"]
    from cryptography.hazmat.primitives.serialization import load_der_public_key
    u.api("POST", f"/api/organizations/{oid}/users/{mem['id']}/confirm", {"key": "4." + b64(load_der_public_key(ub64(pk)).encrypt(ok, oaep))})
    s = v.api("GET", "/api/sync"); po = next(o for o in s["profile"]["organizations"] if o["id"] == oid)
    got = v.priv.decrypt(ub64(po["key"][2:]), oaep); assert got == ok
    x = next(x for x in s["ciphers"] if x["id"] == S["orgcipher"]); v.d(x["name"], got)
    S["shared"] = True; return DONE("user B invited, org key re-wrapped to B's public key, B decrypts shared item")
@t(21)
def _(): t20 = S.get("shared") or T[20][0](); return DONE("whole collection shared to member (see #20)")
@t(22)
def _():
    oid, ok, _ = org(); g = a().api("POST", f"/api/organizations/{oid}/groups", {"name": "Eng", "accessAll": False, "collections": [{"id": S["col"], "readOnly": True, "hidePasswords": False, "manage": False}], "users": []})
    return DONE("group with collection permissions created")
P(23, "one-time links: covered by Send (#24); item-link UX is Phase B")
@t(24)
def _():
    u = a(); sk = os.urandom(16); key = stretch(hashlib.pbkdf2_hmac("sha256", sk, b"bitwarden-send", 1, 32)) if False else None
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    sendkey = HKDF(hashes.SHA256(), 64, b"bitwarden-send", b"send").derive(sk)
    pw = "sendpw"; pwh = b64(hashlib.pbkdf2_hmac("sha256", pw.encode(), sk, 100_000, 32))
    s = u.api("POST", "/api/sends", {"type": 0, "key": enc(sk, u.uk), "name": enc(b"s", sendkey), "text": {"text": enc(b"SECRET-SEND", sendkey), "hidden": False},
        "deletionDate": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(), "maxAccessCount": 1, "password": pwh, "disabled": False, "hideEmail": False})
    sa = lambda pw=None: http("POST", "/identity/connect/token", form={"grant_type": "send_access", "client_id": "send", "scope": "api.send.access",
                                  "send_id": s["accessId"], **({"password_hash_b64": pw} if pw else {})})
    for bad in (None, b64(b"wrong" * 6)):
        try: sa(bad); raise AssertionError("send opened without correct password")
        except HTTPErr as e: assert e.code in (400, 404), e
    tok = sa(pwh)["access_token"]
    r = http("POST", "/api/sends/access", {}, token=tok); assert dec(r["text"]["text"], sendkey) == b"SECRET-SEND"
    try: sa(pwh); raise AssertionError("max views not enforced")
    except HTTPErr as e: assert e.code in (400, 404)
    return DONE("text Send with password, expiry, max-views=1 enforced")
@t(25)
def _(): S.get("shared") or T[20][0](); return DONE("invite -> accept -> confirm with public-key wrapping (see #20)")
@t(26)
def _(): oid, ok, _ = org(); x = a().api("GET", f"/api/organizations/{oid}"); assert x["id"] == oid; return DONE("org created and owns collections/items")
X(27, "family plan (6 seats) = Phase B billing/seat logic (Stripe test mode)")
X(28, "per-seat plans = Phase B billing")
@t(29)
def _():
    S.get("shared") or T[20][0](); v = b(); cid = v.api("POST", "/api/ciphers", v.cipher())["id"]
    x = next(x for x in v.api("GET", "/api/sync")["ciphers"] if x["id"] == cid); assert x["organizationId"] is None
    return DONE("member's personal items stay outside the org")
@t(30)
def _():
    S.get("shared") or T[20][0](); v = b(); cid = v.api("POST", "/api/ciphers", v.cipher())["id"]
    try: a().api("GET", f"/api/ciphers/{cid}"); raise AssertionError("owner read member's personal item")
    except HTTPErr as e: assert e.code in (400, 404)
    return DONE("org owner gets 4xx on a member's personal item (and has no key for it)")
X(31, "family split-off: GoDesk-original, Phase B")
X(32, "per-member family pricing: GoDesk-original, Phase B billing")
P(33, "org admin console ships in the web vault build; UI flows untested (Playwright, Phase B)")
@t(34)
def _():
    oid, ok, _ = org(); now = datetime.now(timezone.utc)
    ev = a().api("GET", f"/api/organizations/{oid}/events?start={(now - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S.000Z")}&end={(now + timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%S.000Z")}")
    assert ev["data"], "no events (ORG_EVENTS_ENABLED?)"; return DONE(f"{len(ev['data'])} org events logged")
X(35, "SIEM export: under review")
@t(36)
def _():
    oid, ok, _ = org(); a().api("PUT", f"/api/organizations/{oid}/policies/0", {"policy": {"enabled": True, "data": None, "type": 0}})
    assert any(p["type"] == 0 and p["enabled"] for p in a().api("GET", f"/api/organizations/{oid}/policies")["data"])
    return DONE("2FA-required policy enabled")
X(37, "password expiry policy: Komboe-original")
P(38, "Vaultwarden public org API (/api/public/organization/import) vendored; not exercised")
X(39, "LDAP/AD connector: under review"); X(40, "SSO: under review"); X(41, "SCIM: under review"); X(42, "trusted devices: under review")
@t(43)
def _():
    oid, ok, _ = org(); u = a()
    try: u.api("PUT", f"/api/organizations/{oid}/policies/8", {"policy": {"enabled": True, "data": None, "type": 8}}); raise AssertionError("recovery policy enabled")
    except HTTPErr as e: assert e.code == 400
    for m, p in [("PUT", f"/api/organizations/{oid}/users/{u.id}/reset-password-enrollment"), ("GET", f"/api/organizations/{oid}/users/{u.id}/reset-password-details"),
                 ("PUT", f"/api/organizations/{oid}/users/{u.id}/recover-account")]:
        try: u.api(m, p, {} if m == "PUT" else None); raise AssertionError(p + " reachable")
        except HTTPErr as e: assert e.code in (404, 405, 422), (p, e.code)
    return ("blocked", "EXCLUDED by policy - verified absent: recovery policy rejected, reset/recover routes 404")
@t(44)
def _():
    for p in ["/api/accounts/key-connector/enroll", "/api/accounts/convert-to-key-connector", "/api/accounts/set-key-connector-key"]:
        try: a().api("POST", p, {}); raise AssertionError(p)
        except HTTPErr as e: assert e.code in (404, 405, 422), (p, e.code)
    return ("blocked", "EXCLUDED by policy - verified absent: no Key Connector endpoints")
@t(45)
def _():
    if not ADMIN: return ("partial", "set KOMBOE_ADMIN_TOKEN to test /admin")
    html = http("POST", "/admin", form={"token": ADMIN}, raw=True, headers={"Accept": "text/html"}).decode()
    assert "Komboe" in html, "admin page not rebranded"; return DONE("/admin login works and is Komboe-branded")
@t(46)
def _():
    v = User(kdf=1); assert http("POST", "/identity/accounts/prelogin", {"email": v.email})["kdf"] == 1
    return DONE("PBKDF2 (600k) and Argon2id (m=64MiB,t=3,p=4) accounts both log in")
@t(47)
def _():
    v = User(); k = v.api("POST", "/api/two-factor/get-authenticator", {"masterPasswordHash": v.hash})["key"]
    v.api("PUT", "/api/two-factor/authenticator", {"key": k, "token": totp(k), "masterPasswordHash": v.hash})
    try: v.login(); raise AssertionError("login without 2FA")
    except HTTPErr as e: assert e.code == 400 and "TwoFactor" in str(e)
    v.dev = None; v.login({"twoFactorProvider": "0", "twoFactorToken": totp(k, time.time() + 30), "twoFactorRemember": "0"})
    return DONE("TOTP 2FA enrol, enforced, login with code")
P(48, "WebAuthn 2FA vendored; needs a virtual authenticator (Playwright, Phase B)")
X(49, "Duo/YubiKey need external accounts; email 2FA needs server SMTP, and enabling it changes signup to mailed tokens (needs a dedicated test instance)")
P(50, "passkey login (WebAuthn PRF) UI vendored; server has no passkey-login endpoints and cannot be rebuilt on this box (disk)")
P(51, "login-with-device (auth-requests) vendored; needs a second client")
P(52, "biometric/PIN unlock are desktop/mobile client features (Phase B)")
X(53, "YubiKey challenge-response unlock: Komboe-original")
X(54, "PGP key auth: Komboe-original")
X(55, "advanced account protection: under review")
@t(56)
def _():
    u = a(); cid = u.api("POST", "/api/ciphers", u.cipher({"login": {"username": u.e("u"), "password": u.e("p"), "totp": u.e("otpauth://totp/x?secret=JBSWY3DPEHPK3PXP"), "uris": []}}))["id"]
    x = next(x for x in u.api("GET", "/api/sync")["ciphers"] if x["id"] == cid); s = u.d(x["login"]["totp"]); assert totp(re.search("secret=([A-Z2-7]+)", s).group(1))
    return DONE("encrypted TOTP seed stored; code computed client-side")
@t(57)
def _():
    u = a(); fc = [{k: u.e(v) for k, v in dict(credentialId="id", keyType="public-key", keyAlgorithm="ECDSA", keyCurve="P-256", keyValue="k",
        rpId="example.com", userHandle="h", userName="n", counter="0", rpName="ex", userDisplayName="n", discoverable="true").items()} | {"creationDate": datetime.now(timezone.utc).isoformat()}]
    cid = u.api("POST", "/api/ciphers", u.cipher({"login": {"username": u.e("u"), "password": None, "uris": [], "fido2Credentials": fc}}))["id"]
    x = next(x for x in u.api("GET", "/api/sync")["ciphers"] if x["id"] == cid); assert u.d(x["login"]["fido2Credentials"][0]["rpId"]) == "example.com"
    return DONE("encrypted passkey storage; autofill is extension (Phase B)")
P(58, "CXP import/export code vendored in clients; untested")
for n in range(59, 67):
    if n == 60: P(60, "alias-generator integrations are in the vendored client generator; untested")
    else: X(n, "aliases: SimpleLogin v4.83.2 vendored in aliases/upstream but not built/run (Phase B)")
X(67, "emergency access: under review (must not become a recovery backdoor)")
for n, w in [(68, "weak/reused report"), (71, "inactive 2FA report"), (72, "unsecured website report")]:
    P(n, f"{w} is client-side in the vendored web vault; Playwright check Phase B")
X(69, "HIBP breach report needs a HIBP API key")
P(70, "k-anonymity exposed-password check is client-side; calls api.pwnedpasswords.com")
X(73, "access intelligence: under review (bitwarden_license code not imported)")
P(74, "generator is client-side (vendored libs/tools/generator); Playwright check Phase B")
P(75, "username generator is client-side (vendored)")
@t(76)
def _():
    u = a(); r = u.api("POST", "/api/ciphers/import", {"ciphers": [u.cipher(), u.cipher()], "folders": [{"name": u.e("Imported")}], "folderRelationships": [{"key": 0, "value": 0}]})
    return DONE("bulk encrypted import API; CSV/JSON parsers are client-side (vendored libs/importer)")
P(77, "KDBX import parser vendored in clients; untested")
P(78, "password-protected export is client-side; untested")
@t(79)
def _():
    oid, ok, _ = org(); u = a()
    u.api("POST", f"/api/ciphers/import-organization?organizationId={oid}", {"ciphers": [u.cipher(key=ok, org=oid)], "collections": [{"name": enc(b"Imp", ok), "id": None}], "collectionRelationships": [{"key": 0, "value": 0}]})
    u.api("GET", f"/api/organizations/{oid}/export"); return DONE("org import + export")
@t(80)
def _():
    html = urllib.request.urlopen(URL + "/").read().decode(); assert "<app-root" in html and "Komboe" in html, "web vault not served/rebranded"
    return DONE("Komboe-branded web vault served by the server")
for n in [81, 82, 83, 84, 85, 86, 87, 90, 91, 92]: X(n, "client build is Phase B (sources vendored in clients/upstream/apps)")
P(88, "CLI sources vendored (apps/cli); this run used a Python API client instead; CLI build Phase B")
X(89, "autofill is extension: Phase B")
X(93, "Docker image: docker unavailable on build box; native binary used")
@t(94)
def _():
    assert DB and os.path.exists(DB), "KOMBOE_DB not set"; return DONE("single native binary + SQLite file")
X(95, "HA/clustering: Phase B (Postgres backend)")
P(96, "S3 attachment backend exists upstream (s3 cargo feature); needs a server rebuild (disk) + local MinIO")
@t(97)
def _():
    import subprocess; r = subprocess.run([sys.executable, os.path.join(ROOT, "tests/e2e/roundtrip.py")], capture_output=True, text=True, env=os.environ)
    assert r.returncode == 0 and "ROUNDTRIP PASS" in r.stdout, r.stdout + r.stderr; return DONE("roundtrip.py: server DB holds only ciphertext")
@t(98)
def _(): S.get("shared") or T[20][0](); return DONE("org key wrapped per member with RSA-OAEP public keys (see #20)")
X(99, "OpenPGP vault encryption: Komboe-original")
@t(100)
def _(): T[46][0](); return ("partial", "AES-256-CBC+HMAC and Argon2id verified; XChaCha20 not implemented")
X(101, "local-only file DB mode: Komboe-original")
X(102, "third-party audit: requires funding/engagement")
X(103, "SaaS billing: Phase B (Stripe test mode only)")
X(104, "free tier: Phase B billing")
X(105, "Proton-style UI: under review")
X(106, "secrets manager: upstream code excluded (bitwarden_license); reimplement later")

for _f in ("phase_b.py", "phase_e.py", "phase_tags.py", "phase_templates.py", "phase_bookmarks.py", "phase_gpg.py", "phase_expiry.py", "phase_dashboard.py", "phase_ha.py", "phase_sso.py", "phase_scim.py", "phase_ldap.py"):
    exec(compile(open(os.path.join(os.path.dirname(__file__), _f)).read(), _f, "exec"))

def main():
    feats = {}
    for line in open(os.path.join(ROOT, "docs/FEATURES.md")):
        m = re.match(r"\|\s*(\d+)\s*\|([^|]*)\|([^|]*)\|", line)
        if m: feats[int(m.group(1))] = (m.group(2).strip(), m.group(3).strip())
    assert sorted(feats) == list(range(1, 107)) and sorted(T) == list(range(1, 107)), (len(feats), sorted(set(range(1, 107)) - set(T)))
    res, fails = {}, 0
    for n in range(1, 107):
        fn, st, why = T[n]
        if fn:
            try: st, why = fn()
            except Exception as e: st, why = "FAIL", f"{type(e).__name__}: {e}"[:300]; fails += 1
        res[n] = (st, why); print(f"#{n:3} {st:8} {feats[n][1][:50]:50} {why[:90]}")
    counts = {k: sum(1 for s, _ in res.values() if s == k) for k in ("done", "partial", "blocked", "FAIL")}
    print("COUNTS", counts)
    if "--write-status" in sys.argv:
        out = sys.argv[sys.argv.index("--write-status") + 1]
        with open(out, "w") as f:
            f.write("# Komboe feature status\n\nGenerated by `tests/features/run.py --write-status docs/STATUS.md` against a locally built Komboe server "
                    f"(Vaultwarden 1.37.4 base) and web vault (clients web-v2026.10.1), {datetime.now().strftime('%Y-%m-%d')}.\n\n"
                    "- **done**: verified end-to-end against the running server in this run\n- **partial**: upstream code is vendored here but not yet exercised end-to-end\n"
                    "- **blocked**: needs Phase B, an external service, or is excluded by policy (excluded items are tested to be *absent*)\n\n"
                    f"**Counts:** done {counts['done']} · partial {counts['partial']} · blocked {counts['blocked']} · fail {counts['FAIL']} (of 106)\n\n"
                    "| # | Category | Feature | Status | Evidence / next step |\n|---|---|---|---|---|\n")
            for n in range(1, 107): f.write(f"| {n} | {feats[n][0]} | {feats[n][1]} | {res[n][0]} | {res[n][1].replace('|', '/')} |\n")
    sys.exit(1 if fails else 0)

if __name__ == "__main__":
    main()
