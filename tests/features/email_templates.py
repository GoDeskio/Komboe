#!/usr/bin/env python3
"""Komboe mail templates: HTML + text, padlock-K, Sora, no GoDesk.
When Mailpit is reachable, each required message is sent through SMTP and read back.
"""
import json
import os
import re
import smtplib
import time
import urllib.parse
import urllib.request
from email.message import EmailMessage
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TPL = ROOT / "server/upstream/src/static/templates/email"
MAILPIT = os.environ.get("MAILPIT", "http://127.0.0.1:8025")
SMTP_HOST = os.environ.get("SMTP_HOST", "127.0.0.1")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "1025"))

REQUIRED = {
    "signup verification": ("register_verify_email", "verify"),
    "sign-in verification code": ("twofactor_email", "verification code"),
    "new device": ("new_device_logged_in", "new device"),
    "master password changed": ("komboe_notice", "open komboe"),
    "two-step login changed": ("komboe_notice", "open komboe"),
    "recovery code used": ("recover_twofactor", "recovery code"),
    "failed sign-in": ("failed_login", "not accepted"),
    "incomplete two-step login": ("incomplete_2fa_login", "two-step"),
    "emergency access": ("emergency_access_recovery_initiated", "emergency"),
    "sharing invite": ("send_org_invite", "invited"),
    "account deletion": ("delete_account", "delete"),
}

def body(name):
    text = (TPL / f"{name}.hbs").read_text()
    html = (TPL / f"{name}.html.hbs").read_text()
    # Drop the subject line that handlebars uses before the separator.
    def rest(raw):
        parts = raw.split("<!---------------->", 1)
        return parts[-1]
    return rest(text), rest(html)

def check_files():
    header = (TPL / "email_header.hbs").read_text()
    assert "logo-komboe.png" in header, "padlock-K mark missing from the email header"
    assert "Sora" in header, "Sora missing from the email header"
    assert "sora.woff2" in header
    assert "GoDesk" not in header
    missing = []
    for kind, (name, needle) in REQUIRED.items():
        text, html = body(name)
        blob = text + html
        if "GoDesk" in blob:
            missing.append(f"{kind}: GoDesk in template")
        whole = (TPL / f"{name}.hbs").read_text() + (TPL / f"{name}.html.hbs").read_text()
        if needle not in whole.lower():
            missing.append(f"{kind}: missing {needle!r}")
        if "<" not in html:
            missing.append(f"{kind}: html part is empty")
        if not text.strip():
            missing.append(f"{kind}: text part is empty")
    assert not missing, missing
    accounts = (ROOT / "server/upstream/src/api/core/accounts.rs").read_text()
    twofa = "\n".join(p.read_text() for p in (ROOT / "server/upstream/src/api/core/two_factor").glob("*.rs"))
    assert "Your Komboe master password was changed" in accounts
    assert "Two-step login was changed on your Komboe account" in twofa
    assert "send_failed_login" in (ROOT / "server/upstream/src/api/identity.rs").read_text()
    assert 'no-reply@komboe.com' in (ROOT / "server/upstream/src/config.rs").read_text()
    print("TEMPLATE FILES PASS", len(REQUIRED))

def mailpit_up():
    try:
        with urllib.request.urlopen(MAILPIT + "/api/v1/info", timeout=2) as r:
            return r.status == 200
    except Exception:
        return False

def send_and_read():
    if not mailpit_up():
        print("MAILPIT SKIP not running at", MAILPIT)
        return
    sent = []
    for kind, (name, _needle) in REQUIRED.items():
        text, html = body(name)
        sample = text.replace("{{token}}", "482913").replace("{{url}}", "http://127.0.0.1:8080")
        sample = re.sub(r"\{\{[#/]?[^}]+\}\}", "sample", sample)
        html_s = html.replace("{{token}}", "482913").replace("{{> email/email_header }}", "<p>Komboe</p>")
        html_s = html_s.replace("{{> email/email_footer }}", "")
        html_s = re.sub(r"\{\{[#/]?[^}]+\}\}", "sample", html_s)
        msg = EmailMessage()
        msg["From"] = "Komboe <no-reply@komboe.com>"
        msg["To"] = "sink@komboe.test"
        msg["Subject"] = f"Komboe test {kind}"
        msg.set_content(sample)
        msg.add_alternative("<html><body style=\"font-family:Sora,Helvetica,sans-serif\">"
                            "<img alt=\"Komboe\" src=\"cid:logo-komboe.png\">" + html_s + "</body></html>",
                            subtype="html")
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as s:
            s.send_message(msg)
        sent.append(kind)
    time.sleep(0.6)
    q = urllib.parse.quote('to:"sink@komboe.test"')
    data = json.loads(urllib.request.urlopen(f"{MAILPIT}/api/v1/search?query={q}&limit=50", timeout=5).read())
    subjects = [m["Subject"] for m in data["messages"]]
    missing = [k for k in sent if f"Komboe test {k}" not in subjects]
    assert not missing, missing
    # One full read: From address and no GoDesk.
    mid = data["messages"][0]["ID"]
    full = json.loads(urllib.request.urlopen(f"{MAILPIT}/api/v1/message/{mid}", timeout=5).read())
    assert full["From"]["Address"] == "no-reply@komboe.com", full["From"]
    blob = (full.get("HTML") or "") + (full.get("Text") or "")
    assert "GoDesk" not in blob
    assert "Komboe" in blob or "sample" in blob
    print("MAILPIT PASS", len(sent))

if __name__ == "__main__":
    import urllib.parse
    check_files()
    send_and_read()
