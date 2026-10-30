# Clean-room enterprise features. Identity protocols never release a vault key.
import base64, socket, subprocess, tempfile, zlib
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding as apad, rsa
from komboe.platform.crypto import dec, enc, enc_str
from komboe.platform.routes.enterprise import _sign_jwt, _verify_jwt
from komboe.platform.server import APIError

OAEP = apad.OAEP(mgf=apad.MGF1(hashes.SHA1()), algorithm=hashes.SHA1(), label=None)

def org_of(u, name="Ent"):
    return http("POST", "/api/organizations", {"name": name}, token=u["token"], base=u["base"])["id"]

@t(40)
def _():
    u = puser(); oid = org_of(u); secret = "sso-must-not-leak-" + uuid.uuid4().hex
    sealed_item(u, 1, {"name": "sso-item", "password": secret})
    idp_pw = "idp-password-" + uuid.uuid4().hex
    email = f"sso-{uuid.uuid4().hex[:8]}@komboe.test"
    http("POST", "/idp/users", {"email": email, "password": idp_pw}, base=u["base"])
    client_secret = "oidc-secret-" + uuid.uuid4().hex
    http("PUT", f"/api/organizations/{oid}/sso", {"protocol": "oidc", "issuer": "komboe-idp", "clientId": "komboe-sp", "clientSecret": client_secret}, token=u["token"], base=u["base"])
    code = http("POST", "/idp/oidc/authorize", {"email": email, "password": idp_pw, "clientId": "komboe-sp", "state": "abc", "nonce": "n1"}, base=u["base"])
    session = http("POST", "/api/sso/oidc/callback", {"organizationId": oid, "code": code["code"]}, base=u["base"])
    assert session["vaultKeyIncluded"] is False and session["userSymmetricKey"] is None and session["protocol"] == "oidc"
    assert secret not in json.dumps(session) and "userKey" not in session
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    evil = _sign_jwt(key, {"email": email, "aud": "komboe-sp", "vaultKey": "nope"})
    try:
        _verify_jwt(key, evil); raise AssertionError("vault key claim accepted")
    except APIError as exc:
        assert exc.status == 400
    cert = http("GET", "/idp/saml/certificate", base=u["base"])["certificate"]
    http("PUT", f"/api/organizations/{oid}/sso", {"protocol": "saml", "issuer": "komboe-idp", "clientId": oid, "certificate": cert}, token=u["token"], base=u["base"])
    request = f'<AuthnRequest ID="_r1" IssueInstant="2026-10-30T00:00:00Z"><Issuer>{oid}</Issuer></AuthnRequest>'
    compressor = zlib.compressobj(wbits=-15)
    saml_request = base64.b64encode(compressor.compress(request.encode()) + compressor.flush()).decode()
    saml = http("POST", "/idp/saml/sso", {"SAMLRequest": saml_request, "email": email, "password": idp_pw, "audience": oid}, base=u["base"])
    got = http("POST", "/api/sso/saml/acs", {"organizationId": oid, "SAMLResponse": saml["SAMLResponse"]}, base=u["base"])
    assert got["protocol"] == "saml" and got["vaultKeyIncluded"] is False and got["userSymmetricKey"] is None
    evil_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    evil_pem = evil_key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    http("PUT", f"/api/organizations/{oid}/sso", {"protocol": "saml", "issuer": "x", "clientId": oid, "certificate": evil_pem}, token=u["token"], base=u["base"])
    assertion = f'<Assertion ID="_e"><Issuer>x</Issuer><Subject><NameID>{email}</NameID></Subject><VaultKey>secret</VaultKey><Conditions><AudienceRestriction><Audience>{oid}</Audience></AudienceRestriction></Conditions></Assertion>'
    sig = base64.b64encode(evil_key.sign(assertion.encode(), apad.PKCS1v15(), hashes.SHA256())).decode()
    blob = base64.b64encode(f'<Response IssueInstant="t">{assertion}<Signature>{sig}</Signature></Response>'.encode()).decode()
    expect(400, http, "POST", "/api/sso/saml/acs", {"organizationId": oid, "SAMLResponse": blob}, base=u["base"])
    absent(u["db"], secret, idp_pw)
    return DONE("OIDC and SAML sign-in establish identity only; assertions that carry a vault key are rejected and the vault secret stays ciphertext")

@t(41)
def _():
    u = puser(); oid = org_of(u)
    token = http("POST", f"/api/organizations/{oid}/scim-token", token=u["token"], base=u["base"])["token"]
    email = f"scim-{uuid.uuid4().hex[:8]}@komboe.test"
    expect(400, http, "POST", "/scim/v2/Users", {"userName": email, "password": "nope"}, headers={"Authorization": "Bearer " + token}, base=u["base"])
    made = http("POST", "/scim/v2/Users", {"userName": email, "active": True}, headers={"Authorization": "Bearer " + token}, base=u["base"])
    assert made["userName"] == email and "password" not in made and "userSymmetricKey" not in json.dumps(made)
    listed = http("GET", "/scim/v2/Users", headers={"Authorization": "Bearer " + token}, base=u["base"])
    assert any(r["id"] == made["id"] for r in listed["Resources"])
    http("PATCH", f"/scim/v2/Users/{made['id']}", {"Operations": [{"op": "replace", "path": "active", "value": False}]}, headers={"Authorization": "Bearer " + token}, base=u["base"])
    row = u["db"].one("SELECT active, user_symmetric_key FROM users WHERE email = ?", (email,))
    assert row["active"] == 0 and row["user_symmetric_key"] is None
    expect(401, http, "POST", "/identity/login", {"email": email, "masterPasswordHash": "x" * 24}, base=u["base"])
    http("DELETE", f"/scim/v2/Users/{made['id']}", headers={"Authorization": "Bearer " + token}, base=u["base"])
    return DONE("SCIM creates, lists, deactivates, and deletes users without passwords or vault keys")

@t(39)
def _():
    u = puser(); oid = org_of(u); directory = tempfile.mkdtemp(prefix="kldap-")
    data = os.path.join(directory, "data"); os.makedirs(data)
    conf = os.path.join(directory, "slapd.conf")
    open(conf, "w").write(f"""include /etc/ldap/schema/core.schema
include /etc/ldap/schema/cosine.schema
include /etc/ldap/schema/inetorgperson.schema
modulepath /usr/lib/ldap
moduleload back_mdb
database mdb
suffix "dc=komboe,dc=test"
rootdn "cn=admin,dc=komboe,dc=test"
rootpw directory-secret
directory {data}
""")
    port = 14000 + (uuid.uuid4().int % 1000)
    proc = subprocess.Popen(["slapd", "-f", conf, "-h", f"ldap://127.0.0.1:{port}", "-d", "0"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        import ldap, time
        conn = None
        for _ in range(30):
            try:
                conn = ldap.initialize(f"ldap://127.0.0.1:{port}")
                conn.simple_bind_s("cn=admin,dc=komboe,dc=test", "directory-secret")
                break
            except ldap.LDAPError:
                time.sleep(0.1)
        assert conn is not None
        suffix = "dc=komboe,dc=test"
        conn.add_s(suffix, [("objectClass", [b"dcObject", b"organization"]), ("dc", [b"komboe"]), ("o", [b"Komboe"])])
        mail = f"ada-{uuid.uuid4().hex[:8]}@komboe.test"
        conn.add_s(f"uid=ada,{suffix}", [("objectClass", [b"inetOrgPerson"]), ("uid", [b"ada"]), ("cn", [b"Ada"]), ("sn", [b"Lovelace"]), ("mail", [mail.encode()])])
        conn.unbind_s()
        http("PUT", f"/api/organizations/{oid}/directory", {"url": f"ldap://127.0.0.1:{port}", "bindDn": "cn=admin,dc=komboe,dc=test", "bindPassword": "directory-secret", "baseDn": suffix, "filter": "(objectClass=inetOrgPerson)"}, token=u["token"], base=u["base"])
        synced = http("POST", f"/api/organizations/{oid}/directory/sync", token=u["token"], base=u["base"])
        assert mail in synced["imported"] and synced["vaultKeyIncluded"] is False
        row = u["db"].one("SELECT user_symmetric_key FROM users WHERE email = ?", (mail,))
        assert row["user_symmetric_key"] is None
    finally:
        proc.terminate()
    return DONE("LDAP directory sync imports account metadata only; imported users have no vault key")

@t(42)
def _():
    u = puser(); other = puser()
    device = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = b64(device.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo))
    wrapped = "4." + b64(device.public_key().encrypt(u["uk"], OAEP))
    enrolled = http("PUT", "/api/devices/trust", {"publicKey": public, "wrappedUserKey": wrapped}, token=u["token"], base=u["base"])
    nonce = os.urandom(32)
    sig = b64(device.sign(nonce, apad.PKCS1v15(), hashes.SHA256()))
    unlocked = http("POST", "/api/devices/unlock", {"deviceId": enrolled["deviceId"], "nonce": b64(nonce), "signature": sig}, token=u["token"], base=u["base"], headers={"X-Komboe-Nonce": b64(nonce)})
    assert unlocked["vaultKeyIncluded"] is False
    assert device.decrypt(ub64(unlocked["wrappedUserKey"][2:]), OAEP) == u["uk"]
    stranger = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    bad = b64(stranger.sign(nonce, apad.PKCS1v15(), hashes.SHA256()))
    expect((401, 404), http, "POST", "/api/devices/unlock", {"deviceId": enrolled["deviceId"], "nonce": b64(nonce), "signature": bad}, token=u["token"], base=u["base"], headers={"X-Komboe-Nonce": b64(nonce)})
    expect(404, http, "POST", "/api/devices/unlock", {"deviceId": enrolled["deviceId"], "nonce": b64(nonce), "signature": sig}, token=other["token"], base=u["base"], headers={"X-Komboe-Nonce": b64(nonce)})
    absent(u["db"], u["uk"])
    return DONE("a trusted device proves its key and receives only the wrapped user key; another device or user cannot unwrap it")

@t(35)
def _():
    u = puser(); oid = org_of(u); secret = "siem-secret-" + uuid.uuid4().hex
    sealed_item(u, 1, {"name": "n", "password": secret})
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 0)); sock.settimeout(2)
    port = sock.getsockname()[1]
    http("PUT", f"/api/organizations/{oid}/siem", {"host": "127.0.0.1", "port": port}, token=u["token"], base=u["base"])
    http("POST", f"/api/organizations/{oid}/events", {"type": "user.logged_in"}, token=u["token"], base=u["base"])
    packet = sock.recv(4096).decode()
    assert "user.logged_in" in packet and secret not in packet and "komboe" in packet
    expect(400, http, "PUT", f"/api/organizations/{oid}/siem", {"host": "203.0.113.9", "port": 514}, token=u["token"], base=u["base"])
    return DONE("org events are exported as syslog to a local collector with metadata only")

@t(55)
def _():
    u = puser()
    for _i in range(4):
        expect(401, http, "POST", "/identity/login", {"email": u["email"], "masterPasswordHash": "not-the-hash"}, base=u["base"])
    expect(429, http, "POST", "/identity/login", {"email": u["email"], "masterPasswordHash": "not-the-hash"}, base=u["base"])
    expect(429, http, "POST", "/identity/login", {"email": u["email"], "masterPasswordHash": password_hash_of(u)}, base=u["base"])
    v = puser()
    first = http("POST", "/identity/login", {"email": v["email"], "masterPasswordHash": password_hash_of(v)}, base=v["base"], headers={"X-Komboe-Device": "dev-a", "X-Komboe-Country": "US"})
    assert "new_device" in first["anomaly"]
    second = http("POST", "/identity/login", {"email": v["email"], "masterPasswordHash": password_hash_of(v)}, base=v["base"], headers={"X-Komboe-Device": "dev-a", "X-Komboe-Country": "DE"})
    assert "impossible_travel" in second["anomaly"] and "new_device" not in second["anomaly"]
    return DONE("five failed logins lock the account; a new device and a fast country change are flagged from metadata only")

def password_hash_of(u):
    from komboe.platform.crypto import master_key, password_hash
    return password_hash(master_key(u["password"], u["email"]), u["password"])

@t(73)
def _():
    u = puser(); oid = org_of(u); secret = "risk-secret-" + uuid.uuid4().hex
    sealed_item(u, 1, {"name": "hidden", "password": secret}, organizationId=oid)
    http("POST", f"/api/organizations/{oid}/members", {"email": "old@komboe.test", "twoFactor": False, "lastSeen": "2020-01-01T00:00:00+00:00"}, token=u["token"], base=u["base"])
    http("POST", f"/api/organizations/{oid}/members", {"email": "new@komboe.test", "twoFactor": True, "accessAll": True}, token=u["token"], base=u["base"])
    report = http("GET", f"/api/organizations/{oid}/risk", token=u["token"], base=u["base"])
    assert "old@komboe.test" in report["membersWithout2fa"] and "old@komboe.test" in report["staleMembers"]
    assert "new@komboe.test" not in report["membersWithout2fa"] and report["collectionsSharedWithEveryone"] == 1
    assert report["vaultReadable"] is False and secret not in json.dumps(report)
    expect(404, http, "GET", f"/api/organizations/{oid}/risk", token=puser()["token"], base=u["base"])
    return DONE("org risk insights count missing 2FA, stale members, and broad access without decrypting items")

@t(106)
def _():
    u = puser(); oid = org_of(u)
    project_key = os.urandom(64)
    secret_value = "machine-secret-" + uuid.uuid4().hex
    project = http("POST", f"/api/organizations/{oid}/secrets/projects", {"name": enc_str("prod-" + uuid.uuid4().hex[:6], u["uk"]), "wrappedProjectKey": enc(project_key, u["uk"])}, token=u["token"], base=u["base"])
    http("POST", f"/api/secrets/projects/{project['id']}/secrets", {"key": enc_str("DB_URL", project_key), "value": enc_str(secret_value, project_key)}, token=u["token"], base=u["base"])
    machine = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = b64(machine.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo))
    wrapped = "4." + b64(machine.public_key().encrypt(project_key, OAEP))
    account = http("POST", f"/api/secrets/projects/{project['id']}/service-accounts", {"name": "deploy", "publicKey": public, "wrappedProjectKey": wrapped}, token=u["token"], base=u["base"])
    got = http("GET", "/api/secrets/machine/secrets", headers={"Authorization": "Bearer " + account["accessToken"]}, base=u["base"])
    opened_key = machine.decrypt(ub64(got["wrappedProjectKey"][2:]), OAEP)
    assert opened_key == project_key
    assert dec(got["secrets"][0]["value"], opened_key).decode() == secret_value
    expect(401, http, "GET", "/api/secrets/machine/secrets", headers={"Authorization": "Bearer sa_wrong"}, base=u["base"])
    absent(u["db"], secret_value, project_key)
    return DONE("secrets manager: project key wrapped to a service account, machine decrypts the secret, plaintext stays out of the DB")
