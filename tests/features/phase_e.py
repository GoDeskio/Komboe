# Phase E feature tests. Loaded into run.py's namespace after phase_b.py.
# Alias mail flow runs against aliases/forwarder (separate process) and a local SMTP sink:
# coverage is LOCAL-TEST (no MX/DNS; custom-domain ownership check skipped via FWD_TRUST_DOMAINS=1).
import smtplib, subprocess, tempfile, time, glob, email as _email
from email import policy as _pol
FWD_DIR = os.path.join(ROOT, "aliases/forwarder")
PYTOOLS = os.environ.get("KOMBOE_PYTOOLS", "/workspace/tools/py")
ADOM = os.environ.get("KOMBOE_ALIAS_DOMAIN", "alias.komboe.localhost")
LT = "LOCAL-TEST (aliases/forwarder + SMTP sink, no MX/DNS): "

def fwd():
    if "fwd" in S: return S["fwd"]
    tmp = tempfile.mkdtemp(prefix="kfwd-"); sink = os.path.join(tmp, "sink")
    env = dict(os.environ, PYTHONPATH=PYTOOLS, SINK_DIR=sink, SINK_PORT="11025", FWD_RELAY="127.0.0.1:11025", FWD_SMTP_PORT="12525",
               FWD_API_PORT="18025", FWD_DB=os.path.join(tmp, "fwd.sqlite3"), FWD_TRUST_DOMAINS="1", KOMBOE_ALIAS_DOMAIN=ADOM)
    procs = [subprocess.Popen([sys.executable, os.path.join(FWD_DIR, f)], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
             for f in ("smtp_sink.py", "komboe_forwarder.py")]
    import atexit; atexit.register(lambda: [p.kill() for p in procs])
    for p in procs: p.stdout.readline()
    S["fwd"] = sink; return sink

def smtp(frm, to, subject, body="hello"):
    m = _email.message.EmailMessage(); m["From"] = frm; m["To"] = to; m["Subject"] = subject; m.set_content(body)
    with smtplib.SMTP("127.0.0.1", 12525, timeout=10) as s: s.sendmail(frm, [to], m.as_bytes())

def inbox(to, subject, n=1, wait=5):
    end = time.time() + wait
    while True:
        got = []
        for p in sorted(glob.glob(os.path.join(fwd(), "*.eml"))):
            m = _email.message_from_bytes(open(p, "rb").read(), policy=_pol.SMTP)
            if to.lower() in m["X-Envelope-To"].lower() and subject in str(m["Subject"]): got.append(m)
        if len(got) >= n or time.time() > end: return got
        time.sleep(0.1)

def fapi(key, m, p, body=None):
    return http(m, p, body, headers={"Authentication": key}, base="http://127.0.0.1:18025")

def new_alias(u=None):
    fwd(); u = u or User(); k = alias_key(u); x = sl(k, "POST", "/api/alias/random/new", {}); return u, k, x

def verify_mailbox(k, addr):
    fapi(k, "POST", "/fwd/mailboxes", {"email": addr})
    code = re.search(r"code: (\d{6})", inbox(addr, "Verify your Komboe mailbox")[-1].get_content()).group(1)
    expect(400, fapi, k, "POST", "/fwd/mailboxes/verify", {"email": addr, "code": "000000" if code != "000000" else "111111"})
    assert fapi(k, "POST", "/fwd/mailboxes/verify", {"email": addr, "code": code})["verified"]

@t(59)
def _():
    u, k, x = new_alias(); smtp("shop@ext.test", x["alias"], "order-59")
    m = inbox(u.email, "order-59"); assert m, "not forwarded"
    assert m[0]["X-Komboe-Alias"] == x["alias"] and f"ra+" in m[0]["From"] and ADOM in m[0]["From"]
    try: smtp("a@ext.test", "nobody-" + x["alias"], "x"); raise AssertionError("unknown alias accepted")
    except smtplib.SMTPRecipientsRefused: pass
    return ("done", LT + "alias created via SimpleLogin API, inbound mail forwarded to the account email with a reverse-alias From; unknown alias 550")

@t(65)
def _():
    u, k, x = new_alias(); aid = x["id"]
    smtp("a@ext.test", x["alias"], "s65-1")
    fapi(k, "POST", f"/fwd/aliases/{aid}/block", {"sender": "spam@ext.test"}); smtp("spam@ext.test", x["alias"], "s65-spam")
    assert sl(k, "POST", f"/api/aliases/{aid}/toggle")["enabled"] is False
    try: smtp("a@ext.test", x["alias"], "s65-off"); raise AssertionError("disabled alias accepted")
    except smtplib.SMTPDataError: pass
    sl(k, "POST", f"/api/aliases/{aid}/toggle"); time.sleep(0.5)
    assert inbox(u.email, "s65-1") and not inbox(u.email, "s65-spam", wait=0) and not inbox(u.email, "s65-off", wait=0)
    st = fapi(k, "GET", f"/fwd/aliases/{aid}/stats"); assert st == {"nb_forward": 1, "nb_block": 2, "nb_reply": 0}, st
    _, k2, _ = new_alias(); expect(404, fapi, k2, "GET", f"/fwd/aliases/{aid}/stats"); expect(401, fapi, "kmb_bad", "GET", f"/fwd/aliases/{aid}/stats")
    return ("done", LT + "enable/disable (server API) enforced at SMTP, block sender drops mail, stats count forward/block; owner-scoped")

@t(62)
def _():
    u, k, x = new_alias(); a, b = f"m1-{u.id[:8]}@home.test", f"m2-{u.id[:8]}@work.test"
    expect(400, fapi, k, "PUT", f"/fwd/aliases/{x['id']}/mailboxes", {"mailboxes": [a]})  # unverified
    verify_mailbox(k, a); verify_mailbox(k, b)
    fapi(k, "PUT", f"/fwd/aliases/{x['id']}/mailboxes", {"mailboxes": [a, b]}); smtp("c@ext.test", x["alias"], "mb62")
    assert inbox(a, "mb62") and inbox(b, "mb62") and not inbox(u.email, "mb62", wait=0)
    return ("done", LT + "mailboxes verified by emailed code, alias forwards to both; unverified mailbox refused")

@t(63)
def _():
    u, k, x = new_alias(); smtp("friend@ext.test", x["alias"], "hi63")
    ra = _email.utils.parseaddr(inbox(u.email, "hi63")[0]["Reply-To"])[1]
    smtp(u.email, ra, "re63", "reply body")
    m = inbox("friend@ext.test", "re63"); assert m and m[0]["From"] == x["alias"] and u.email not in m[0].as_string()
    try: smtp("intruder@ext.test", ra, "re63-x"); raise AssertionError("non-mailbox sender relayed")
    except smtplib.SMTPDataError: pass
    assert fapi(k, "GET", f"/fwd/aliases/{x['id']}/stats")["nb_reply"] == 1
    return ("done", LT + "reply via ra+ reverse alias goes out From the alias, real address hidden; only alias mailboxes may use it (prod also needs SPF/DKIM checks)")

@t(64)
def _():
    u, k, x = new_alias(); mb = f"pgp-{u.id[:8]}@home.test"; verify_mailbox(k, mb)
    home = tempfile.mkdtemp(prefix="kgpg-"); env = dict(os.environ, GNUPGHOME=home)
    subprocess.run(["gpg", "--batch", "--passphrase", "", "--quick-gen-key", mb, "default", "default", "1d"], env=env, check=True, capture_output=True)
    pub = subprocess.run(["gpg", "--armor", "--export", mb], env=env, check=True, capture_output=True, text=True).stdout
    expect(400, fapi, k, "PUT", f"/fwd/mailboxes/{mb}/pgp", {"publicKey": "nope"})
    fapi(k, "PUT", f"/fwd/mailboxes/{mb}/pgp", {"publicKey": pub}); fapi(k, "PUT", f"/fwd/aliases/{x['id']}/mailboxes", {"mailboxes": [mb]})
    smtp("bank@ext.test", x["alias"], "pgp64", "secret statement 4242")
    m = inbox(mb, "pgp64")[0]; raw = m.as_string()
    assert m.get_content_type() == "multipart/encrypted" and "secret statement 4242" not in raw
    ct = m.get_payload()[1].get_payload(decode=True)
    pt = subprocess.run(["gpg", "--batch", "--decrypt"], input=ct, env=env, check=True, capture_output=True).stdout.decode()
    assert "secret statement 4242" in pt
    return ("done", LT + "forwarded mail PGP/MIME-encrypted (RFC 3156) to the mailbox key; decrypts with gpg; plaintext absent in transit copy")

@t(61)
def _():
    u, k, _ = new_alias(); d = f"d{u.id[:8]}.test"
    expect(400, fapi, k, "POST", "/fwd/domains", {"domain": "x." + ADOM})
    r = fapi(k, "POST", "/fwd/domains", {"domain": d, "catchAll": True}); assert r["txtRecord"].startswith("komboe-verify=")
    smtp("a@ext.test", f"anything@{d}", "ca61"); assert inbox(u.email, "ca61")
    _, k2, _ = new_alias(); expect(409, fapi, k2, "POST", "/fwd/domains", {"domain": d})
    return ("done", LT + "custom domain with catch-all forwards any local part; domain bound to one owner; DNS TXT verification skipped (FWD_TRUST_DOMAINS=1)")

@t(66)
def _():
    u, k, _ = new_alias(); s = f"s{u.id[:8]}"
    assert fapi(k, "POST", "/fwd/subdomains", {"name": s})["subdomain"] == f"{s}.{ADOM}"
    smtp("a@ext.test", f"newsletter@{s}.{ADOM}", "sd66"); assert inbox(u.email, "sd66")
    _, k2, _ = new_alias(); expect(409, fapi, k2, "POST", "/fwd/subdomains", {"name": s})
    return ("done", LT + "directory subdomain <name>." + ADOM + " creates aliases on the fly; names unique per owner")

@t(23)
def _():
    T[24][0]()  # one-time (max views 1) + password
    u = a(); sk = os.urandom(16)
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    skey = HKDF(hashes.SHA256(), 64, b"bitwarden-send", b"send").derive(sk); now = datetime.now(timezone.utc)
    s = u.api("POST", "/api/sends", {"type": 0, "key": enc(sk, u.uk), "name": enc(b"e", skey), "text": {"text": enc(b"EXP", skey), "hidden": False},
        "deletionDate": (now + timedelta(days=1)).isoformat(), "expirationDate": (now + timedelta(seconds=3)).isoformat(), "disabled": False, "hideEmail": False})
    sa = lambda: http("POST", "/identity/connect/token", form={"grant_type": "send_access", "client_id": "send", "scope": "api.send.access", "send_id": s["accessId"]})
    sa(); time.sleep(4)
    expect((400, 404), sa)
    return DONE("expiring link: Send opens before expirationDate, refused after; one-time max-views=1 via #24")

@t(51)
def _():
    from cryptography.hazmat.primitives.serialization import load_der_public_key as _ldp
    u = User(); out = {}
    for approve in (True, False):
        dpriv = rsa.generate_private_key(public_exponent=65537, key_size=2048); dev = str(uuid.uuid4()); code = uuid.uuid4().hex[:25]
        http("POST", "/identity/connect/token", form={"grant_type": "password", "username": u.email, "password": u.hash, "scope": "api offline_access",
             "client_id": "cli", "deviceType": "8", "deviceIdentifier": dev, "deviceName": "new"})  # server only accepts requests from a device it has seen
        pub = b64(dpriv.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo))
        r = http("POST", "/api/auth-requests", {"email": u.email, "publicKey": pub, "deviceIdentifier": dev, "accessCode": code, "type": 0},
                 headers={"Device-Identifier": dev, "Device-Type": "8"})
        assert any(x["id"] == r["id"] for x in u.api("GET", "/api/auth-requests")["data"])
        wrapped = "4." + b64(_ldp(ub64(pub)).encrypt(u.uk, OAEP)) if approve else ""
        u.api("PUT", f"/api/auth-requests/{r['id']}", {"key": wrapped, "masterPasswordHash": None, "deviceIdentifier": u.dev, "requestApproved": approve})
        resp_ = lambda: http("GET", f"/api/auth-requests/{r['id']}/response?code={code}", headers={"Device-Identifier": dev, "Device-Type": "8"})
        tok = lambda: http("POST", "/identity/connect/token", form={"grant_type": "password", "username": u.email, "password": code,
            "authRequest": r["id"], "scope": "api offline_access", "client_id": "cli", "deviceType": "8", "deviceIdentifier": dev, "deviceName": "new"})
        if approve:
            resp = resp_(); assert resp["requestApproved"] and dpriv.decrypt(ub64(resp["key"][2:]), OAEP) == u.uk  # new device recovers the user key E2E
            assert tok()["access_token"]
        else:
            try: resp = resp_(); assert not resp.get("requestApproved") and not resp.get("key")
            except HTTPErr as e: assert e.code in (400, 404)  # denied requests are deleted
            expect((400, 401), tok)
    return DONE("login with device: new device's request approved by a logged-in device, user key RSA-OAEP-wrapped to the new device (server never sees it); denied request gets no token (requesting device must be known to the server, as in Vaultwarden)")

@t(9)
def _():
    import subprocess; p = art("komboe-linux-x64"); cert = "/workspace/run/tls/cert.pem"
    u = User(); u.api("POST", "/api/ciphers", u.cipher({"name": u.e("offline-item")})); d = tempfile.mkdtemp()
    env = dict(os.environ, XDG_CONFIG_HOME=d, NODE_EXTRA_CA_CERTS=cert, KPW=u.pw); env.pop("BITWARDENCLI_APPDATA_DIR", None)
    run = lambda *a, e=env: subprocess.run([p, *a], capture_output=True, text=True, timeout=120, env=e)
    run("config", "server", os.environ.get("KOMBOE_TLS_URL", "https://localhost:8443"))
    sess = run("login", u.email, "--passwordenv", "KPW", "--raw").stdout.strip().splitlines()[-1]
    assert run("sync", "--session", sess).returncode == 0
    off = dict(env, HTTPS_PROXY="http://127.0.0.1:9", HTTP_PROXY="http://127.0.0.1:9", https_proxy="http://127.0.0.1:9", NO_PROXY="")
    assert run("sync", "--session", sess, e=off).returncode != 0, "network not actually cut"
    items = json.loads(run("list", "items", "--session", sess, e=off).stdout)
    assert [i["name"] for i in items] == ["offline-item"]
    return DONE("CLI: after one sync the encrypted vault cache decrypts and lists items with the network cut (sync fails, list works)")

@t(77)
def _():
    import subprocess; p = art("komboe-linux-x64"); cert = "/workspace/run/tls/cert.pem"; d = tempfile.mkdtemp()
    x = os.path.join(d, "kp.xml"); open(x, "w").write("""<?xml version="1.0" encoding="utf-8"?><KeePassFile><Root><Group><Name>Root</Name>
<Entry><String><Key>Title</Key><Value>kp-entry</Value></String><String><Key>UserName</Key><Value>alice</Value></String>
<String><Key>Password</Key><Value ProtectInMemory="True">kp-secret-77</Value></String><String><Key>URL</Key><Value>https://kp.test</Value></String></Entry>
</Group></Root></KeePassFile>""")
    u = User(); env = dict(os.environ, XDG_CONFIG_HOME=d, NODE_EXTRA_CA_CERTS=cert, KPW=u.pw); env.pop("BITWARDENCLI_APPDATA_DIR", None)
    run = lambda *a: subprocess.run([p, *a], capture_output=True, text=True, timeout=120, env=env)
    run("config", "server", os.environ.get("KOMBOE_TLS_URL", "https://localhost:8443"))
    sess = run("login", u.email, "--passwordenv", "KPW", "--raw").stdout.strip().splitlines()[-1]
    r = run("import", "keepass2xml", x, "--session", sess); assert r.returncode == 0, r.stdout + r.stderr
    ck = lambda c: dec(c["key"], u.uk) if c.get("key") else None  # per-item cipher key
    c = [c for c in u.api("GET", "/api/sync")["ciphers"] if u.d(c["name"], ck(c)) == "kp-entry"]
    assert c and u.d(c[0]["login"]["password"], ck(c[0])) == "kp-secret-77"
    k = subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "kdbx_cli.py"), *os.environ.get("KOMBOE_CLI_SRC", "").split()], capture_output=True, text=True, timeout=600)
    if k.returncode != 0:
        raise RuntimeError((k.stdout + k.stderr)[-800:])
    return ("done", "KeePass 2 XML + native .kdbx import via CLI (SDK), stored encrypted; `bw export --format kdbx` writes a password-protected KDBX 4 read back by pykeepass and re-imported (tests/features/kdbx_cli.py)")
