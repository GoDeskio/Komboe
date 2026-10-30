# Emergency access that cannot decrypt without the grantor's prior key share.
import time
from komboe.platform.crypto import dec, enc, master_key, password_hash
def _flow(grantor, grantee, access, wait, wrapped):
    body = {"granteeEmail": grantee["email"], "type": access, "waitSeconds": wait}
    if wrapped is not None:
        body["keyEncrypted"] = wrapped
    grant = http("POST", "/api/emergency", body, token=grantor["token"], base=grantor["base"])
    http("POST", f"/api/emergency/{grant['id']}/accept", token=grantee["token"], base=grantor["base"])
    http("POST", f"/api/emergency/{grant['id']}/confirm", token=grantor["token"], base=grantor["base"])
    http("POST", f"/api/emergency/{grant['id']}/initiate", token=grantee["token"], base=grantor["base"])
    return grant

@t(67)
def _():
    grantor, grantee, stranger = puser(), puser(), puser()
    secret = "emergency-secret-" + uuid.uuid4().hex
    made = sealed_item(grantor, 1, {"name": "shared-later", "password": secret})
    bare = _flow(grantor, grantee, "view", 1, None)
    expect(403, http, "POST", f"/api/emergency/{bare['id']}/view", token=grantee["token"], base=grantor["base"])
    time.sleep(1.2)
    err = expect(403, http, "POST", f"/api/emergency/{bare['id']}/view", token=grantee["token"], base=grantor["base"])
    assert "prior key share" in str(err)
    takeover = _flow(grantor, grantee, "takeover", 1, None)
    time.sleep(1.2)
    expect(403, http, "POST", f"/api/emergency/{takeover['id']}/takeover", {"newMasterPasswordHash": "x" * 24, "wrappedUserKey": enc(b"nope", grantee["uk"])}, token=grantee["token"], base=grantor["base"])
    assert http("POST", "/identity/login", {"email": grantor["email"], "masterPasswordHash": password_hash(master_key(grantor["password"], grantor["email"]), grantor["password"])}, base=grantor["base"])["accessToken"]
    shared = enc(grantor["uk"], grantee["uk"])
    live = _flow(grantor, grantee, "view", 1, shared)
    expect(403, http, "POST", f"/api/emergency/{live['id']}/view", token=grantee["token"], base=grantor["base"])
    time.sleep(1.2)
    opened = http("POST", f"/api/emergency/{live['id']}/view", token=grantee["token"], base=grantor["base"])
    assert opened["vaultKeyIncluded"] is False
    assert dec(opened["keyEncrypted"], grantee["uk"]) == grantor["uk"]
    row = next(c for c in opened["ciphers"] if c["id"] == made["id"])
    assert secret not in json.dumps(opened)
    assert dec(row["data"], grantor["uk"]).decode().find(secret) >= 0
    expect(404, http, "POST", f"/api/emergency/{live['id']}/view", token=stranger["token"], base=grantor["base"])
    for path in ("/api/accounts/key-connector/enroll", "/api/emergency/admin-recover"):
        expect((404, 405), http, "POST", path, {}, token=stranger["token"], base=grantor["base"])
    absent(grantor["db"], grantor["uk"], secret)
    return DONE("emergency view decrypts only a grantor-wrapped key after the wait; a grant with no key share never decrypts, and there is no admin recovery")
