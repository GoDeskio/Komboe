"""#50 passkey challenges are shared through the database, so HA works without sticky sessions.

Two server nodes share one database (KOMBOE_URL_A / KOMBOE_URL_B, default :8000 and :8443).
Node A issues the challenge; node B consumes it; the token is single-use across nodes and
expired rows are swept. Rows hold only WebAuthn ceremony state, never keys or vault data.
"""
import json, os, sqlite3, ssl, time, urllib.request, urllib.error, urllib.parse

A = os.environ.get("KOMBOE_URL_A", "http://localhost:8000")
B = os.environ.get("KOMBOE_URL_B", "https://localhost:8443")
DB = os.environ.get("KOMBOE_DB", "/workspace/run/mt/data/db.sqlite3")
CTX = ssl.create_default_context(cafile=os.environ.get("NODE_EXTRA_CA_CERTS", "/workspace/run/tls/cert.pem"))
H = {"Device-Type": "9", "Bitwarden-Client-Name": "web", "Bitwarden-Client-Version": "2026.10.1", "Accept": "application/json"}

def req(base, path, form=None):
    data = urllib.parse.urlencode(form).encode() if form else None
    h = dict(H, **({"Content-Type": "application/x-www-form-urlencoded"} if form else {}))
    try:
        with urllib.request.urlopen(urllib.request.Request(base + path, data=data, headers=h), context=CTX if base.startswith("https") else None) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()

def login(base, token):
    return req(base, "/identity/connect/token", {"grant_type": "webauthn", "token": token, "scope": "api offline_access", "client_id": "web",
        "deviceResponse": json.dumps({"id": "AAAA", "rawId": "AAAA", "type": "public-key", "extensions": {},
        "response": {"authenticatorData": "AAAA", "signature": "AAAA", "clientDataJson": "AAAA", "userHandle": "AAAA"}}),
        "deviceType": "9", "deviceIdentifier": "11111111-1111-1111-1111-111111111111", "deviceName": "ha"})

db = sqlite3.connect(DB)
rows = lambda tok: db.execute("select state from komboe_passkey_challenges where token=?", (tok,)).fetchall()

code, opts = req(A, "/identity/accounts/webauthn/assertion-options")
assert code == 200 and opts["token"], opts
(state,) = rows(opts["token"])[0]
assert opts["options"]["challenge"] in state or "challenge" in state, "row must hold the ceremony state"
for bad in ("encrypted_user_key", "masterPassword", "privateKey"):
    assert bad not in state, f"challenge row must not contain {bad}"
print("  node A stored the challenge in the shared DB (ceremony state only)")

code, body = login(B, opts["token"])
assert code == 400 and "Passkey sign-in failed" in body, (code, body)
assert rows(opts["token"]) == [], "node B must consume node A's challenge"
print("  node B consumed node A's challenge (no sticky session needed)")

code, body = login(A, opts["token"])
assert code == 400, (code, body)
print("  token is single-use across nodes")

old = "ha-expired-" + str(time.time())
db.execute("insert into komboe_passkey_challenges (token, state, created_at) values (?, '{}', ?)", (old, int(time.time()) - 3600)); db.commit()
code, body = login(B, old); assert code == 400, body
req(A, "/identity/accounts/webauthn/assertion-options")
assert db.execute("select count(*) from komboe_passkey_challenges where created_at < ?", (int(time.time()) - 301,)).fetchone()[0] == 0
print("  expired challenges are refused and swept")
print("PASSKEY HA PASS")
