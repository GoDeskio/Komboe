"""Live feature checks for the first security/server unblock batch."""
import http.server as _hs
import socket
import socketserver
import sqlite3
import threading


@t(35)
def _():
    oid, _, _ = org(); secret = "feature-test-hmac-" + uuid.uuid4().hex
    got = {}
    class Handler(_hs.BaseHTTPRequestHandler):
        def do_POST(self):
            n = int(self.headers.get("Content-Length", "0")); got["body"] = self.rfile.read(n)
            got["sig"] = self.headers.get("X-Komboe-Signature"); self.send_response(204); self.end_headers()
        def log_message(self, *_): pass
    with socketserver.TCPServer(("127.0.0.1", 0), Handler) as listener:
        thread = threading.Thread(target=listener.handle_request, daemon=True); thread.start()
        endpoint = f"http://127.0.0.1:{listener.server_address[1]}/events"
        r = a().api("PUT", f"/api/komboe/organizations/{oid}/siem",
                    {"kind": "webhook", "endpoint": endpoint, "hmacSecret": secret, "enabled": True})
        assert r["hmacConfigured"] and "secret" not in json.dumps(r).lower()
        a().api("POST", f"/api/komboe/organizations/{oid}/siem/test", {})
        thread.join(5); assert got.get("body"), "SIEM listener received nothing"
        expected = "sha256=" + hmac.new(secret.encode(), got["body"], hashlib.sha256).hexdigest()
        assert hmac.compare_digest(got["sig"], expected)
        event = json.loads(got["body"]); assert event["schema"] == "komboe.siem.v1" and "cipher" not in event
    tcp = socket.socket(); tcp.bind(("127.0.0.1", 0)); tcp.listen(1); syslog = {}
    def receive_syslog():
        conn, _ = tcp.accept()
        with conn: syslog["data"] = conn.recv(65536)
    thread = threading.Thread(target=receive_syslog, daemon=True); thread.start()
    a().api("PUT", f"/api/komboe/organizations/{oid}/siem", {"kind":"syslog","endpoint":f"tcp://127.0.0.1:{tcp.getsockname()[1]}","enabled":True})
    a().api("POST", f"/api/komboe/organizations/{oid}/siem/test", {}); thread.join(5); tcp.close()
    assert syslog.get("data", b"").startswith(b"<134>1 ") and b'"schema":"komboe.siem.v1"' in syslog["data"]
    return DONE("local RFC5424 TCP listener + HMAC webhook received sanitized event envelopes")


@t(55)
def _():
    u = User(); device = str(uuid.uuid4()); form = {"grant_type":"password","username":u.email,"password":u.hash,
        "scope":"api offline_access","client_id":"cli","deviceType":"8","deviceIdentifier":device,"deviceName":"risk-test"}
    for ip in ("203.0.113.10", "198.51.100.20"):
        try: http("POST", "/identity/connect/token", form=form, headers={"X-Real-IP":ip})
        except HTTPErr as e: assert e.code == 400 and os.environ.get("KOMBOE_ANOMALY_STEP_UP") == "true"
    form["password"] = "bad-password-hash"
    for _n in range(5):
        try: http("POST", "/identity/connect/token", form=form, headers={"X-Real-IP":"198.51.100.20"})
        except HTTPErr as e: assert e.code in (400, 429)
    rows = u.api("GET", "/api/komboe/anomalies")["data"]
    kinds = {x["type"] for x in rows}
    assert {"new_device_and_network", "impossible_travel", "repeated_failures"} <= kinds, rows
    return DONE("new device+prefix, rapid prefix change, and five failures recorded as anomalies")


@t(67)
def _():
    grantor, grantee = User(), User(); grantor.api("POST", "/api/ciphers", grantor.cipher())
    grantor.api("POST", "/api/emergency-access/invite", {"email":grantee.email,"type":0,"waitTimeDays":1})
    ea = next(x for x in grantor.api("GET", "/api/emergency-access/trusted")["data"] if x["email"] == grantee.email)
    if ea["status"] == 0:
        message = mailpit(grantee.email, "Emergency")
        token = urllib.parse.unquote(re.search(r"token=([^&\"'\s<]+)", message["Text"] + message["HTML"]).group(1))
        grantee.api("POST", f"/api/emergency-access/{ea['id']}/accept", {"token": token})
    from cryptography.hazmat.primitives.serialization import load_der_public_key
    pk = grantor.api("GET", f"/api/users/{grantee.id}/public-key")["publicKey"]
    oaep = apad.OAEP(mgf=apad.MGF1(hashes.SHA1()), algorithm=hashes.SHA1(), label=None)
    wrapped = "4." + b64(load_der_public_key(ub64(pk)).encrypt(grantor.uk, oaep))
    grantor.api("POST", f"/api/emergency-access/{ea['id']}/confirm", {"key":wrapped})
    grantee.api("POST", f"/api/emergency-access/{ea['id']}/initiate", {})
    try: grantee.api("POST", f"/api/emergency-access/{ea['id']}/view", {}); raise AssertionError("view before wait")
    except HTTPErr as e: assert e.code == 400
    for suffix in ("takeover", "password", "policies", "approve"):
        try: grantee.api("POST", f"/api/emergency-access/{ea['id']}/{suffix}", {}); raise AssertionError(suffix)
        except HTTPErr as e: assert e.code in (404, 405), (suffix, e.code)
    assert DB, "KOMBOE_DB required to age the wait-period fixture"
    old = (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(DB) as db: db.execute("UPDATE emergency_access SET recovery_initiated_at=? WHERE uuid=?", (old, ea["id"])); db.commit()
    view = grantee.api("POST", f"/api/emergency-access/{ea['id']}/view", {})
    assert view["ciphers"] and view["keyEncrypted"] == wrapped
    grantor.api("POST", f"/api/emergency-access/{ea['id']}/reject", {})
    return DONE("view denied before wait, allowed after wait with grantor-confirmed key; takeover/reset routes absent")


@t(73)
def _():
    oid, _, _ = org(); report = a().api("GET", f"/api/komboe/organizations/{oid}/risk-report")
    assert report["metadataOnly"] is True and report["vaultDataRead"] is False
    assert isinstance(report["membersWithout2fa"], list) and isinstance(report["sharedItemCount"], int)
    assert not any(k in json.dumps(report).lower() for k in ("password\"", "ciphertext", "privatekey"))
    return DONE("metadata-only org risk report: 2FA, stale, broad access, shared row count")


def _signed_stripe(oid, event_type="checkout.session.completed"):
    secret = os.environ.get("STRIPE_WEBHOOK_SECRET"); assert secret, "STRIPE_WEBHOOK_SECRET required"
    body = json.dumps({"id":"evt_test_"+uuid.uuid4().hex,"type":event_type,
        "data":{"object":{"metadata":{"organization_id":oid}}}}, separators=(",",":"))
    ts = int(time.time()); sig = hmac.new(secret.encode(), f"{ts}.{body}".encode(), hashlib.sha256).hexdigest()
    headers = {"Content-Type":"application/json", "Stripe-Signature":f"t={ts},v1={sig}"}
    req = urllib.request.Request(URL+"/api/komboe/billing/stripe-webhook", data=body.encode(), method="POST", headers=headers)
    return json.loads(urllib.request.urlopen(req).read())


@t(103)
def _():
    if not os.environ.get("STRIPE_SECRET_KEY", "").startswith("sk_test_") or not os.environ.get("STRIPE_WEBHOOK_SECRET"):
        return ("partial", "server implementation present; rerun with sk_test_ STRIPE_SECRET_KEY and STRIPE_WEBHOOK_SECRET")
    oid, _, _ = org(); checkout = a().api("POST", f"/api/komboe/organizations/{oid}/billing/checkout", {"plan":"team","interval":"annual"})
    assert checkout["id"].startswith("cs_test_") and checkout["testMode"] is True
    try:
        http("POST", "/api/komboe/billing/stripe-webhook", {"type":"checkout.session.completed"}, headers={"Stripe-Signature":"t=1,v1=bad"})
        raise AssertionError("bad Stripe signature accepted")
    except HTTPErr as e: assert e.code == 400
    assert _signed_stripe(oid)["status"] == "active"
    assert a().api("GET", f"/api/komboe/organizations/{oid}/billing")["status"] == "active"
    return DONE("test checkout + annual plan + timestamped webhook HMAC; invalid signature rejected")


def _fresh_org(u):
    ok=os.urandom(64); oaep=apad.OAEP(mgf=apad.MGF1(hashes.SHA1()),algorithm=hashes.SHA1(),label=None)
    wrapped="4."+b64(u.priv.public_key().encrypt(ok,oaep)); priv=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    return u.api("POST","/api/organizations",{"name":"Free Limit","billingEmail":u.email,"key":wrapped,"planType":0,
        "collectionName":enc(b"Default",ok),"keys":{"publicKey":b64(priv.public_key().public_bytes(serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo)),
        "encryptedPrivateKey":enc(priv.private_bytes(serialization.Encoding.DER,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()),ok)}})["id"]


@t(104)
def _():
    u=User(); oid=_fresh_org(u); plan=u.api("GET",f"/api/komboe/organizations/{oid}/plan")
    assert plan["kind"]=="free" and plan["seats"]==3
    for n in range(2): u.api("POST",f"/api/organizations/{oid}/users/invite",{"emails":[f"free-{n}-{uuid.uuid4().hex}@komboe.test"],"type":2,"collections":[],"accessAll":False,"permissions":{},"groups":[]})
    try:
        u.api("POST",f"/api/organizations/{oid}/users/invite",{"emails":[f"over-{uuid.uuid4().hex}@komboe.test"],"type":2,"collections":[],"accessAll":False,"permissions":{},"groups":[]})
        raise AssertionError("free seat limit not enforced")
    except HTTPErr as e: assert e.code == 400
    return DONE("free plan defaults to three seats and rejects the fourth member")


@t(106)
def _():
    oid,_,_=org(); u=a(); p=u.api("POST",f"/api/komboe/organizations/{oid}/projects",{"name":"Deploy"})
    ciphertext="enc.v1."+base64.b64encode(os.urandom(48)).decode(); s=u.api("POST",f"/api/komboe/projects/{p['id']}/secrets",{"name":"API_KEY","ciphertext":ciphertext})
    assert s["ciphertext"]==ciphertext and s["serverCanDecrypt"] is False
    sa=u.api("POST",f"/api/komboe/projects/{p['id']}/service-accounts",{"name":"ci"}); assert sa["token"].startswith("ksm_")
    r=http("GET","/api/komboe/service/v1/secrets",headers={"Authorization":"Bearer "+sa["token"]})
    assert any(x["id"]==s["id"] and x["ciphertext"]==ciphertext for x in r["data"])
    u.api("DELETE",f"/api/komboe/projects/{p['id']}/service-accounts/{sa['id']}")
    try: http("GET","/api/komboe/service/v1/secrets",headers={"Authorization":"Bearer "+sa["token"]}); raise AssertionError("revoked token worked")
    except HTTPErr as e: assert e.code in (400,401)
    return DONE("ciphertext-only project secret; scoped one-time service token; revocation enforced")


@t(93)
def _():
    text=open(os.path.join(ROOT,"docker/Dockerfile.server")).read()
    for needle in ("FROM rust:","FROM debian:","USER 10001:10001","HEALTHCHECK","--locked","ENTRYPOINT"):
        assert needle in text, needle
    ignore=open(os.path.join(ROOT,"docker/Dockerfile.server.dockerignore")).read()
    assert "**" in ignore and "!server/upstream/src/**" in ignore
    # Do not COPY a host target/ tree into the image (cargo's own target/ path in RUN is fine).
    assert not re.search(r"(?m)^COPY\s+.*\btarget\b", text), "Dockerfile must not COPY host target/"
    assert "/out/komboe" in text and "USER 10001:10001" in text
    return ("partial", "multi-stage/non-root/healthchecked Dockerfile statically verified; Docker is unavailable on this build box")
