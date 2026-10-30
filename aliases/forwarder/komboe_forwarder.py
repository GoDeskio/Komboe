#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Komboe alias mail forwarder (Komboe-original).

A separate process next to the Komboe server. It reads aliases from the server DB
(read-only: komboe_aliases, komboe_alias_keys, users) and keeps its own state
(mailboxes, blocks, stats, reverse aliases, domains, subdomains, PGP keys) in FWD_DB.

  SMTP in  (FWD_SMTP_PORT): mail to <alias>@<domain>, catch-all custom domains,
           <anything>@<sub>.<ALIAS_DOMAIN>, and reverse aliases ra+<token>@<ALIAS_DOMAIN>.
  SMTP out (FWD_RELAY host:port): the next hop. In local tests this is a sink.
  HTTP API (FWD_API_PORT): owner-scoped management, authenticated with the same
           kmb_ alias API key the server issues (sha256 lookup in komboe_alias_keys).

Mail content is never stored; only counters and reverse-alias mappings are.
Domain ownership needs a DNS TXT check in production. Local tests set
FWD_TRUST_DOMAINS=1 to skip it; that mode refuses to start unless bound to loopback.
"""
import asyncio, hashlib, json, os, re, secrets, smtplib, sqlite3, subprocess, sys, tempfile, threading, time, uuid
from email import message_from_bytes, policy
from email.message import EmailMessage
from email.utils import parseaddr, formataddr
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ENV = os.environ.get
SERVER_DB, FWD_DB = ENV("KOMBOE_DB", "data/db.sqlite3"), ENV("FWD_DB", "forwarder.sqlite3")
DOMAIN = ENV("KOMBOE_ALIAS_DOMAIN", "alias.komboe.localhost").lower()
BIND = ENV("FWD_BIND", "127.0.0.1")
RELAY = ENV("FWD_RELAY", "127.0.0.1:1025")
TRUST_DOMAINS = ENV("FWD_TRUST_DOMAINS") == "1"

SCHEMA = """
CREATE TABLE IF NOT EXISTS mailboxes (user_uuid TEXT, email TEXT, verified INT, code TEXT, pgp TEXT, PRIMARY KEY(user_uuid, email));
CREATE TABLE IF NOT EXISTS alias_mailboxes (alias_uuid TEXT, email TEXT, PRIMARY KEY(alias_uuid, email));
CREATE TABLE IF NOT EXISTS blocks (alias_uuid TEXT, sender TEXT, PRIMARY KEY(alias_uuid, sender));
CREATE TABLE IF NOT EXISTS stats (alias_uuid TEXT PRIMARY KEY, forwarded INT DEFAULT 0, blocked INT DEFAULT 0, replied INT DEFAULT 0);
CREATE TABLE IF NOT EXISTS contacts (token TEXT PRIMARY KEY, alias_uuid TEXT, alias_email TEXT, contact TEXT, UNIQUE(alias_uuid, contact));
CREATE TABLE IF NOT EXISTS domains (domain TEXT PRIMARY KEY, user_uuid TEXT, catch_all INT, verified INT, txt TEXT);
CREATE TABLE IF NOT EXISTS subdomains (name TEXT PRIMARY KEY, user_uuid TEXT);
"""
_lock = threading.Lock()
def fdb():
    c = sqlite3.connect(FWD_DB, isolation_level=None); c.executescript(SCHEMA); return c
def sdb(): return sqlite3.connect(f"file:{SERVER_DB}?mode=ro", uri=True)

def bump(alias_uuid, col):
    with _lock:
        c = fdb(); c.execute("INSERT OR IGNORE INTO stats(alias_uuid) VALUES (?)", (alias_uuid,))
        c.execute(f"UPDATE stats SET {col}={col}+1 WHERE alias_uuid=?", (alias_uuid,))

def user_email(uid):
    r = sdb().execute("SELECT email FROM users WHERE uuid=?", (uid,)).fetchone(); return r and r[0]

def resolve(rcpt):
    """-> (alias_uuid, alias_email, user_uuid, enabled) or None"""
    rcpt = rcpt.lower(); local, _, dom = rcpt.partition("@")
    r = sdb().execute("SELECT uuid, email, user_uuid, enabled FROM komboe_aliases WHERE lower(email)=?", (rcpt,)).fetchone()
    if r: return r[0], r[1], r[2], bool(r[3])
    c = fdb()
    d = c.execute("SELECT user_uuid FROM domains WHERE domain=? AND verified=1 AND catch_all=1", (dom,)).fetchone()
    if not d and dom.endswith("." + DOMAIN):
        d = c.execute("SELECT user_uuid FROM subdomains WHERE name=?", (dom[: -len(DOMAIN) - 1],)).fetchone()
    if d: return "auto:" + rcpt, rcpt, d[0], True   # auto-created on first use; stats keyed by address
    return None

def mailboxes(alias_uuid, uid):
    c = fdb()
    m = [r[0] for r in c.execute("SELECT am.email FROM alias_mailboxes am JOIN mailboxes m ON m.email=am.email AND m.user_uuid=? "
                                  "WHERE am.alias_uuid=? AND m.verified=1", (uid, alias_uuid))]
    return m or [user_email(uid)]

def contact_token(alias_uuid, alias_email, contact):
    with _lock:
        c = fdb(); r = c.execute("SELECT token FROM contacts WHERE alias_uuid=? AND contact=?", (alias_uuid, contact)).fetchone()
        if r: return r[0]
        tok = secrets.token_hex(12); c.execute("INSERT INTO contacts VALUES (?,?,?,?)", (tok, alias_uuid, alias_email, contact)); return tok

def send(frm, to, msg_bytes):
    h, p = RELAY.rsplit(":", 1)
    with smtplib.SMTP(h, int(p), timeout=15) as s: s.sendmail(frm, to, msg_bytes)

def pgp_wrap(msg, armored_key):
    """RFC 3156 PGP/MIME: encrypt the whole original MIME body to the mailbox key."""
    with tempfile.TemporaryDirectory() as home:
        env = dict(os.environ, GNUPGHOME=home)
        subprocess.run(["gpg", "--batch", "--quiet", "--import"], input=armored_key.encode(), env=env, check=True, capture_output=True)
        fpr = re.search(r"^fpr:+([0-9A-F]+):", subprocess.run(["gpg", "--batch", "--with-colons", "--list-keys"], env=env,
                        capture_output=True, text=True, check=True).stdout, re.M).group(1)
        inner = EmailMessage(policy=policy.SMTP); inner.set_content(msg.get_body(("plain", "html")).get_content() if msg.get_body(("plain", "html")) else "")
        ct = subprocess.run(["gpg", "--batch", "--quiet", "--trust-model", "always", "--armor", "--encrypt", "-r", fpr],
                            input=inner.as_bytes(), env=env, check=True, capture_output=True).stdout.decode()
    out = EmailMessage(policy=policy.SMTP)
    for k in ("From", "To", "Subject", "Reply-To", "Date", "Message-ID"):
        if msg[k]: out[k] = msg[k]
    out.set_type("multipart/encrypted"); out.set_param("protocol", "application/pgp-encrypted")
    v = EmailMessage(); v.set_content("Version: 1\n"); v.replace_header("Content-Type", "application/pgp-encrypted")
    b = EmailMessage(); b.set_content(ct); b.replace_header("Content-Type", 'application/octet-stream; name="encrypted.asc"')
    out.set_payload([v, b]); return out

class Handler:
    async def handle_RCPT(self, server, session, envelope, address, rcpt_options):
        a = address.lower()
        if a.startswith("ra+") and a.endswith("@" + DOMAIN) or resolve(a):
            envelope.rcpt_tos.append(address); return "250 OK"
        return "550 5.1.1 no such alias"
    async def handle_DATA(self, server, session, envelope):
        try:
            for rcpt in envelope.rcpt_tos: self.deliver(envelope.mail_from or "", rcpt, envelope.content)
            return "250 OK"
        except Rejected as e: return f"550 {e}"
    def deliver(self, mail_from, rcpt, raw):
        msg = message_from_bytes(raw, policy=policy.SMTP); rl = rcpt.lower()
        if rl.startswith("ra+"):   # reply from the user's mailbox to a contact, sent as the alias
            r = fdb().execute("SELECT alias_uuid, alias_email, contact FROM contacts WHERE token=?", (rl[3:].split("@")[0],)).fetchone()
            if not r: raise Rejected("unknown reverse alias")
            al = resolve(r[1])
            if not al or mail_from.lower() not in [m.lower() for m in mailboxes(al[0], al[2])]: raise Rejected("sender is not a mailbox of this alias")
            for h in ("From", "Sender", "Reply-To"): del msg[h]
            msg["From"] = r[1]; del msg["To"]; msg["To"] = r[2]
            send(r[1], [r[2]], msg.as_bytes()); bump(r[0], "replied"); return
        al = resolve(rl)
        if not al: raise Rejected("no such alias")
        aid, aemail, uid, enabled = al; sender = parseaddr(msg.get("From", mail_from))[1].lower() or mail_from.lower()
        if not enabled: bump(aid, "blocked"); raise Rejected("alias disabled")
        if fdb().execute("SELECT 1 FROM blocks WHERE alias_uuid=? AND sender=?", (aid, sender)).fetchone():
            bump(aid, "blocked"); return   # accepted and silently dropped, like SimpleLogin
        name = parseaddr(msg.get("From", ""))[0] or sender
        ra = f"ra+{contact_token(aid, aemail, sender)}@{DOMAIN}"
        del msg["From"]; del msg["Reply-To"]; msg["From"] = formataddr((f"{name} via Komboe", ra)); msg["Reply-To"] = ra
        msg["X-Komboe-Alias"] = aemail
        for mb in mailboxes(aid, uid):
            key = fdb().execute("SELECT pgp FROM mailboxes WHERE user_uuid=? AND email=? AND verified=1", (uid, mb)).fetchone()
            out = pgp_wrap(msg, key[0]) if key and key[0] else msg
            send(ra, [mb], out.as_bytes())
        bump(aid, "forwarded")
class Rejected(Exception): pass

# ---------------- HTTP API ----------------
def owner_of(key):
    if not key: return None
    r = sdb().execute("SELECT user_uuid FROM komboe_alias_keys WHERE key_hash=?", (hashlib.sha256(key.strip().encode()).hexdigest(),)).fetchone()
    return r and r[0]
def own_alias(uid, aid):
    r = sdb().execute("SELECT email FROM komboe_aliases WHERE uuid=? AND user_uuid=?", (aid, uid)).fetchone(); return r and r[0]
DOM_RE = re.compile(r"^(?=.{1,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")

class Api(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def reply(self, code, obj):
        b = json.dumps(obj).encode(); self.send_response(code); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self): self.route("GET")
    def do_POST(self): self.route("POST")
    def do_PUT(self): self.route("PUT")
    def do_DELETE(self): self.route("DELETE")
    def route(self, m):
        uid = owner_of(self.headers.get("Authentication"))
        if not uid: return self.reply(401, {"error": "bad api key"})
        n = int(self.headers.get("Content-Length") or 0)
        try: body = json.loads(self.rfile.read(n) or b"{}")
        except ValueError: return self.reply(400, {"error": "bad json"})
        p = self.path.split("?")[0].rstrip("/"); c = fdb()
        def alias_or_404(aid):
            e = own_alias(uid, aid)
            if not e: self.reply(404, {"error": "not found"})
            return e
        if m == "POST" and p == "/fwd/mailboxes":
            e = str(body.get("email", "")).strip().lower()
            if "@" not in e: return self.reply(400, {"error": "email"})
            code = f"{secrets.randbelow(10**6):06d}"
            with _lock: c.execute("INSERT OR REPLACE INTO mailboxes(user_uuid,email,verified,code,pgp) VALUES (?,?,0,?,NULL)", (uid, e, code))
            vm = EmailMessage(); vm["From"] = f"noreply@{DOMAIN}"; vm["To"] = e; vm["Subject"] = "Verify your Komboe mailbox"
            vm.set_content(f"Your Komboe mailbox verification code: {code}\n"); send(f"noreply@{DOMAIN}", [e], vm.as_bytes())
            return self.reply(200, {"email": e, "verified": False})
        if m == "POST" and p == "/fwd/mailboxes/verify":
            e = str(body.get("email", "")).lower(); r = c.execute("SELECT code FROM mailboxes WHERE user_uuid=? AND email=?", (uid, e)).fetchone()
            if not r or not r[0] or not secrets.compare_digest(r[0], str(body.get("code", ""))): return self.reply(400, {"error": "bad code"})
            c.execute("UPDATE mailboxes SET verified=1, code=NULL WHERE user_uuid=? AND email=?", (uid, e)); return self.reply(200, {"email": e, "verified": True})
        mm = re.fullmatch(r"/fwd/mailboxes/([^/]+)/pgp", p)
        if m == "PUT" and mm:
            e = mm.group(1).lower(); k = str(body.get("publicKey", ""))
            if "BEGIN PGP PUBLIC KEY BLOCK" not in k: return self.reply(400, {"error": "publicKey"})
            if not c.execute("UPDATE mailboxes SET pgp=? WHERE user_uuid=? AND email=? AND verified=1", (k, uid, e)).rowcount:
                return self.reply(404, {"error": "verified mailbox not found"})
            return self.reply(200, {"email": e, "pgp": True})
        ma = re.fullmatch(r"/fwd/aliases/([0-9a-f-]{36})/(mailboxes|block|stats|unblock)", p)
        if ma:
            aid, op = ma.groups()
            if not alias_or_404(aid): return
            if op == "mailboxes" and m == "PUT":
                ms = [str(x).lower() for x in body.get("mailboxes", [])]
                ok = {r[0] for r in c.execute("SELECT email FROM mailboxes WHERE user_uuid=? AND verified=1", (uid,))}
                if not ms or not set(ms) <= ok: return self.reply(400, {"error": "every mailbox must be verified first"})
                with _lock:
                    c.execute("DELETE FROM alias_mailboxes WHERE alias_uuid=?", (aid,))
                    c.executemany("INSERT INTO alias_mailboxes VALUES (?,?)", [(aid, x) for x in ms])
                return self.reply(200, {"mailboxes": ms})
            if op in ("block", "unblock") and m == "POST":
                s = str(body.get("sender", "")).lower()
                c.execute("INSERT OR IGNORE INTO blocks VALUES (?,?)" if op == "block" else "DELETE FROM blocks WHERE alias_uuid=? AND sender=?", (aid, s))
                return self.reply(200, {"sender": s, "blocked": op == "block"})
            if op == "stats" and m == "GET":
                r = c.execute("SELECT forwarded, blocked, replied FROM stats WHERE alias_uuid=?", (aid,)).fetchone() or (0, 0, 0)
                return self.reply(200, dict(zip(("nb_forward", "nb_block", "nb_reply"), r)))
        if m == "POST" and p == "/fwd/domains":
            d = str(body.get("domain", "")).lower()
            if not DOM_RE.match(d) or d == DOMAIN or d.endswith("." + DOMAIN): return self.reply(400, {"error": "domain"})
            if c.execute("SELECT user_uuid FROM domains WHERE domain=? AND user_uuid<>?", (d, uid)).fetchone(): return self.reply(409, {"error": "taken"})
            txt = "komboe-verify=" + secrets.token_hex(16)
            c.execute("INSERT OR REPLACE INTO domains VALUES (?,?,?,?,?)", (d, uid, int(bool(body.get("catchAll"))), int(TRUST_DOMAINS), txt))
            return self.reply(200, {"domain": d, "catchAll": bool(body.get("catchAll")), "verified": TRUST_DOMAINS, "txtRecord": txt})
        if m == "POST" and p == "/fwd/subdomains":
            s = str(body.get("name", "")).lower()
            if not re.fullmatch(r"[a-z0-9]([a-z0-9-]{1,30}[a-z0-9])", s): return self.reply(400, {"error": "name"})
            try: c.execute("INSERT INTO subdomains VALUES (?,?)", (s, uid))
            except sqlite3.IntegrityError: return self.reply(409, {"error": "taken"})
            return self.reply(200, {"subdomain": f"{s}.{DOMAIN}"})
        return self.reply(404, {"error": "no route"})

def main():
    from aiosmtpd.controller import Controller
    if TRUST_DOMAINS and BIND not in ("127.0.0.1", "::1", "localhost"): sys.exit("FWD_TRUST_DOMAINS=1 is local-test only; bind to loopback")
    fdb()
    ctl = Controller(Handler(), hostname=BIND, port=int(ENV("FWD_SMTP_PORT", "2525"))); ctl.start()
    api = ThreadingHTTPServer((BIND, int(ENV("FWD_API_PORT", "8025"))), Api)
    print(f"komboe-forwarder smtp={BIND}:{ctl.port} api={BIND}:{api.server_port} relay={RELAY}", flush=True)
    try: api.serve_forever()
    finally: ctl.stop()

if __name__ == "__main__": main()
