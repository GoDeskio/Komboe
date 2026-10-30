#!/usr/bin/env python3
"""Komboe email E2E: trigger every notification against a local test server with SMTP -> Mailpit,
then check each captured mail: Komboe From name, Komboe branding, no Bitwarden/Vaultwarden text,
and links pointing at DOMAIN / komboe.com (tokens in links are used against the API where the flow allows).

Usage: . /workspace/run/mt/env.sh-equivalent; KOMBOE_URL=http://127.0.0.1:8000 KOMBOE_ADMIN_TOKEN=... python3 tests/features/emails.py
LOCAL/TEST ONLY - never point at production.
"""
import os, sys, re, json, time, uuid, hashlib, subprocess, tempfile, smtplib, html as _html
sys.argv = [sys.argv[0]]
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
os.environ.setdefault("KOMBOE_SMTP", "1")
import run as R
from run import http, HTTPErr, User, mailpit, enc, b64, ub64, stretch, URL, ADMIN
ns = vars(R)
from cryptography.hazmat.primitives.serialization import load_der_public_key
assert "127.0.0.1" in URL or "localhost" in URL, "emails.py is local/test only"
BAD = re.compile(r"bitwarden|vaultwarden", re.I)
RES = []

def check(kind, to, subj, extra=None):
    m = mailpit(to, subj)
    body = (m.get("HTML") or "") + "\n" + (m.get("Text") or "")
    probs = []
    if (m["From"].get("Name") or "") != "Komboe": probs.append(f"From name {m['From'].get('Name')!r}")
    for where, txt in (("subject", m["Subject"]), ("body", body)):
        hit = BAD.search(txt)
        if hit: probs.append(f"{hit.group(0)} in {where}: ...{txt[max(0,hit.start()-40):hit.end()+40]!r}")
    if "Komboe" not in body + m["Subject"]: probs.append("no Komboe branding")
    links = set(_html.unescape(u) for u in re.findall(r'href="([^"]+)"', m.get("HTML") or "")) | set(re.findall(r"https?://[^\s<>\"')]+", m.get("Text") or ""))
    for u in links:
        if not (u.startswith(URL) or re.match(r"https?://(www\.)?komboe\.com", u) or u.startswith("mailto:")): probs.append(f"foreign link {u}")
    if extra:
        try: extra(m, body)
        except Exception as e: probs.append(f"{type(e).__name__}: {e}"[:200])
    RES.append((kind, "PASS" if not probs else "FAIL", m["Subject"], "; ".join(probs)[:400], len(links)))
    return m, body

def tok_from(body, name="token"):
    return _html.unescape(__import__("urllib.parse").parse.unquote(re.search(name + r"=([^&\"'\s<]+)", body).group(1)))

def step(kind, fn):
    try: fn()
    except Exception as e: RES.append((kind, "FAIL", "-", f"{type(e).__name__}: {e}"[:400], 0))

def admin_user():
    env = dict(l.strip().split("=", 1) for l in open("/home/box/.secrets/komboe-test-admin.env") if "=" in l)
    try: return User(email=env["KOMBOE_TEST_ADMIN_EMAIL"], pw=env["KOMBOE_TEST_ADMIN_PASSWORD"])
    except (HTTPErr, AssertionError):  # already registered (no new verify mail): just log in
        u = User.__new__(User); u.email = env["KOMBOE_TEST_ADMIN_EMAIL"]; u.pw = env["KOMBOE_TEST_ADMIN_PASSWORD"]
        pre = http("POST", "/identity/accounts/prelogin", {"email": u.email}); u.it = pre["kdfIterations"]
        u.mk = hashlib.pbkdf2_hmac("sha256", u.pw.encode(), u.email.encode(), u.it, 32); u.hash = b64(hashlib.pbkdf2_hmac("sha256", u.mk, u.pw.encode(), 1, 32))
        u.login(); from run import dec
        from cryptography.hazmat.primitives.serialization import load_der_private_key
        prof = u.api("GET", "/api/accounts/profile"); u.uk = dec(prof["key"], stretch(u.mk))
        u.priv = load_der_private_key(dec(prof["privateKey"], u.uk), None); return u

def main():
    A = {}
    def reg():
        A["u"] = admin_user(); v = User()  # fresh address so a verify mail is always sent this run
        check("registration verify email", v.email, "Verify"); A["v"] = v
    step("registration verify email", reg)
    step("welcome", lambda: check("welcome", A["v"].email, "Welcome"))
    def newdev():
        u = A["u"]; u.dev = None; u.login(); check("new-device login", u.email, "New Device")
    step("new-device login", newdev)
    def verify():
        u = User(); u.api("POST", "/api/accounts/verify-email")
        check("verify email (resend)", u.email, "Verify Your Email", lambda m, b: None)
    step("verify email (resend)", verify)
    def twofa():
        u = User(); A["tf"] = u
        u.api("POST", "/api/two-factor/send-email", {"email": u.email, "masterPasswordHash": u.hash})
        m, b = check("2FA email code (setup)", u.email, "Login Verification Code" , lambda m, b: re.search(r"\b\d{6}\b", m["Text"]))
        code = re.search(r"\b(\d{6})\b", m["Text"]).group(1)
        u.api("PUT", "/api/two-factor/email", {"email": u.email, "token": code, "masterPasswordHash": u.hash})
        try: u.login(); raise AssertionError("login without 2FA code succeeded")
        except HTTPErr as e: assert e.code == 400
        def used(m, b):
            c = re.search(r"\b(\d{6})\b", m["Text"]).group(1); u.login({"twoFactorProvider": "1", "twoFactorToken": c})
        time.sleep(1.1)  # newest mail must be the login code, not the setup code
        http("POST", "/api/two-factor/send-email-login", {"email": u.email, "masterPasswordHash": u.hash})
        time.sleep(0.5); check("2FA email code (login)", u.email, "Login Verification Code", used)
    step("2FA email code", twofa)
    def hint():
        u = User(); http("POST", "/api/accounts/password-hint", {"email": u.email}); check("password hint (none set)", u.email, "no password hint")
        nmk = hashlib.pbkdf2_hmac("sha256", u.pw.encode(), u.email.encode(), u.it, 32)  # same password, now with a hint
        u.api("POST", "/api/accounts/password", {"masterPasswordHash": u.hash, "newMasterPasswordHash": u.hash, "masterPasswordHint": "komboe-hint-xyz", "key": enc(u.uk, stretch(nmk))})
        time.sleep(1.1)
        http("POST", "/api/accounts/password-hint", {"email": u.email})
        check("password hint", u.email, "Hint", lambda m, b: "komboe-hint-xyz" in b or (_ for _ in ()).throw(AssertionError("hint text missing")))
    step("password hint", hint)
    def pwchange():
        u = User(); npw = "Komboe-FT-new-" + uuid.uuid4().hex
        nmk = hashlib.pbkdf2_hmac("sha256", npw.encode(), u.email.encode(), u.it, 32); nh = b64(hashlib.pbkdf2_hmac("sha256", nmk, npw.encode(), 1, 32))
        u.api("POST", "/api/accounts/password", {"masterPasswordHash": u.hash, "newMasterPasswordHash": nh, "masterPasswordHint": None, "key": enc(u.uk, stretch(nmk))})
        u.hash = nh; check("master password change", u.email, "master password was changed", lambda m, b: u.login())
    step("master password change", pwchange)
    def chemail():
        u = User(); new = f"ft-new-{uuid.uuid4().hex[:8]}@komboe.test"
        u.api("POST", "/api/accounts/email-token", {"newEmail": new, "masterPasswordHash": u.hash})
        check("change email token", new, "Email Change")
    step("change email token", chemail)
    def delrec():
        u = User(); http("POST", "/api/accounts/delete-recover", {"email": u.email})
        def link(m, b): assert "delete" in b.lower() and tok_from(b)
        check("delete account", u.email, "Delete", link)
    step("delete account", delrec)
    # org invite / accepted / confirmed / 2FA-policy removal
    def orgflow():
        o = A["u"]; v = User(); oid, ok = ns["mkorg"](o, "Mail Org")
        o.api("POST", f"/api/organizations/{oid}/users/invite", {"emails": [v.email], "type": 2, "collections": [], "accessAll": False, "permissions": {}, "groups": []})
        mem = next(x for x in o.api("GET", f"/api/organizations/{oid}/users")["data"] if x["email"] == v.email)
        def accept(m, b):
            t = tok_from(b); v.api("POST", f"/api/organizations/{oid}/users/{mem['id']}/accept", {"token": t, "resetPasswordKey": None})
        check("org invite", v.email, "Join", accept)
        check("org invite accepted (to admin)", o.email, "Mail Org accepted")
        pk = o.api("GET", f"/api/users/{v.id}/public-key")["publicKey"]
        o.api("POST", f"/api/organizations/{oid}/users/{mem['id']}/confirm", {"key": "4." + b64(load_der_public_key(ub64(pk)).encrypt(ok, ns["OAEP"]))})
        check("org invite confirmed", v.email, "Mail Org confirmed")
        A["org"] = (oid, ok)
    step("org invites", orgflow)
    def emergency():
        g, e = User(), User()
        g.api("POST", "/api/emergency-access/invite", {"email": e.email, "type": 1, "waitTimeDays": 1})
        ea = g.api("GET", "/api/emergency-access/trusted")["data"][0]
        check("emergency invite", e.email, "Emergency", lambda m, b: e.api("POST", f"/api/emergency-access/{ea['id']}/accept", {"token": tok_from(b)}))
        check("emergency accepted (to grantor)", g.email, "Accepted")
        pk = g.api("GET", f"/api/users/{e.id}/public-key")["publicKey"]
        g.api("POST", f"/api/emergency-access/{ea['id']}/confirm", {"key": "4." + b64(load_der_public_key(ub64(pk)).encrypt(g.uk, ns["OAEP"]))})
        check("emergency confirmed", e.email, "Confirmed")
        e.api("POST", f"/api/emergency-access/{ea['id']}/initiate"); check("emergency recovery initiated", g.email, "Initiated")
        g.api("POST", f"/api/emergency-access/{ea['id']}/reject"); check("emergency recovery rejected", e.email, "Rejected")
        e.api("POST", f"/api/emergency-access/{ea['id']}/initiate"); g.api("POST", f"/api/emergency-access/{ea['id']}/approve")
        check("emergency recovery approved", e.email, "Approved")
    step("emergency access", emergency)
    def send():
        u = User(); sk = os.urandom(16)
        from cryptography.hazmat.primitives.kdf.hkdf import HKDF; from cryptography.hazmat.primitives import hashes
        from datetime import datetime, timedelta, timezone
        k = HKDF(hashes.SHA256(), 64, b"bitwarden-send", b"send").derive(sk)
        s = u.api("POST", "/api/sends", {"type": 0, "key": enc(sk, u.uk), "name": enc(b"s", k), "text": {"text": enc(b"x", k), "hidden": False},
            "deletionDate": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(), "maxAccessCount": 3, "disabled": False, "hideEmail": False})
        tok = http("POST", "/identity/connect/token", form={"grant_type": "send_access", "client_id": "send", "scope": "api.send.access", "send_id": s["accessId"]})["access_token"]
        http("POST", "/api/sends/access", {}, token=tok); check("Send opened", u.email, "Send was opened", lambda m, b: re.search(r"1 of 3", b) or (_ for _ in ()).throw(AssertionError("no view count")))
    step("Send notification", send)
    def split():
        o = User(); kid = User(); oid, ok = ns["mkorg"](o, "Mail Family")
        o.api("PUT", f"/api/komboe/organizations/{oid}/plan", {"kind": "family", "seats": 3, "pricePerMemberCents": 150})
        check("billing notice (plan updated)", o.email, "Billing notice", lambda m, b: re.search(r"seat", b, re.I) or (_ for _ in ()).throw(AssertionError("no seats")))
        ns["add_member"](o, oid, ok, kid)
        r = kid.api("POST", f"/api/komboe/organizations/{oid}/split-requests", {"note": "mail test"})
        check("split-off request (to admin)", o.email, "split")
        check("split-off request (to requester)", kid.email, "split")
        o.api("POST", f"/api/komboe/split-requests/{r['id']}/approve"); check("split-off approved", kid.email, "approved")
        nid, _ = ns["mkorg"](kid, "Kid Fam"); kid.api("POST", f"/api/komboe/split-requests/{r['id']}/complete", {"newOrganizationId": nid})
        check("split-off completed (to user)", kid.email, "family is ready"); check("split-off completed (to old admins)", o.email, "A member left")
        r2_o, kid2 = o, User(); ns["add_member"](o, oid, ok, kid2)
        r2 = kid2.api("POST", f"/api/komboe/organizations/{oid}/split-requests", {"note": "deny me"}); o.api("POST", f"/api/komboe/split-requests/{r2['id']}/deny")
        check("split-off declined", kid2.email, "declined")
    step("split-off + billing", split)
    def smtptest():
        import urllib.request, urllib.parse
        op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())
        op.open(urllib.request.Request(URL + "/admin", data=urllib.parse.urlencode({"token": ADMIN}).encode()))
        to = f"smtp-test-{uuid.uuid4().hex[:6]}@komboe.test"
        op.open(urllib.request.Request(URL + "/admin/test/smtp", data=json.dumps({"email": to}).encode(), headers={"Content-Type": "application/json"}))
        check("admin SMTP test", to, "")
    step("admin SMTP test", smtptest)
    def alias():
        tmp = tempfile.mkdtemp(prefix="kfwd-mp-")
        env = dict(os.environ, PYTHONPATH=ns["PYTOOLS"], FWD_RELAY="127.0.0.1:1025", FWD_SMTP_PORT="12625", FWD_API_PORT="18125",
                   FWD_DB=os.path.join(tmp, "fwd.sqlite3"), KOMBOE_DB=os.environ.get("KOMBOE_DB", "/workspace/run/mt/data/db.sqlite3"), FWD_TRUST_DOMAINS="1", KOMBOE_ALIAS_DOMAIN=ns["ADOM"])
        p = subprocess.Popen([sys.executable, os.path.join(ns["FWD_DIR"], "komboe_forwarder.py")], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        try:
            p.stdout.readline(); u = User(); k = ns["alias_key"](u)
            fapi = lambda m, pth, body=None: http(m, pth, body, headers={"Authentication": k}, base="http://127.0.0.1:18125")
            x = ns["sl"](k, "POST", "/api/alias/random/new", {})
            m = __import__("email").message.EmailMessage(); m["From"] = "shop@ext.test"; m["To"] = x["alias"]; m["Subject"] = "alias-fwd-" + uuid.uuid4().hex[:6]; m.set_content("hi")
            with smtplib.SMTP("127.0.0.1", 12625, timeout=10) as s: s.send_message(m)
            got = mailpit(u.email, m["Subject"]); RES.append(("alias forwarding", "PASS" if not BAD.search(json.dumps(got.get("Text",""))) else "FAIL", got["Subject"], "via forwarder relay -> Mailpit (From name is the original sender by design)", 0))
        finally: p.kill()
    step("alias forwarding", alias)
    w = max(len(r[0]) for r in RES)
    for k, st, subj, why, nl in RES: print(f"{st:4} {k:{w}} | {subj[:60]:60} | links={nl} {why}")
    print("TOTAL", sum(r[1] == "PASS" for r in RES), "pass /", len(RES))
    json.dump(RES, open("/workspace/run/mt/emails-result.json", "w"), indent=1)
    sys.exit(0 if all(r[1] == "PASS" for r in RES) else 1)

main()
