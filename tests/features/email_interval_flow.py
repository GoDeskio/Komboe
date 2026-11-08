#!/usr/bin/env python3
"""Server login exercise for the timed email code. Uses a loopback SMTP sink and a throwaway database."""
import hashlib
import os
import re
import shutil
import socket
import sqlite3
import subprocess
import tempfile
import threading
import time
import urllib.parse
import urllib.request
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BIN = Path(os.environ.get("KOMBOE_BIN", ROOT / "server/upstream/target/debug/vaultwarden"))
API = "http://127.0.0.1:18081"
SINK_PORT = 12526


class Sink(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.messages = []
        self._stop = threading.Event()
        self.sock = socket.socket()
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", SINK_PORT))
        self.sock.listen(8)
        self.sock.settimeout(0.3)

    def run(self):
        while not self._stop.is_set():
            try:
                conn, _ = self.sock.accept()
            except socket.timeout:
                continue
            threading.Thread(target=self._client, args=(conn,), daemon=True).start()

    def _client(self, conn):
        try:
            conn.sendall(b"220 komboe test sink\r\n")
            buf = b""
            data = False
            body = b""
            while True:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                buf += chunk
                while b"\r\n" in buf:
                    line, buf = buf.split(b"\r\n", 1)
                    if data:
                        if line == b".":
                            self.messages.append(body)
                            body = b""
                            data = False
                            conn.sendall(b"250 ok\r\n")
                        else:
                            body += line + b"\r\n"
                        continue
                    cmd = line.upper()
                    if cmd.startswith(b"DATA"):
                        data = True
                        conn.sendall(b"354 go\r\n")
                    elif cmd.startswith(b"QUIT"):
                        conn.sendall(b"221 bye\r\n")
                        return
                    else:
                        conn.sendall(b"250 ok\r\n")
        except OSError:
            pass
        finally:
            conn.close()

    def stop(self):
        self._stop.set()
        self.sock.close()


def b64(raw: bytes) -> str:
    import base64
    return base64.b64encode(raw).decode()


def password_hash(email: str, password: str, iterations: int = 100000) -> str:
    master = hashlib.pbkdf2_hmac("sha256", password.encode(), email.encode(), iterations, 32)
    return b64(hashlib.pbkdf2_hmac("sha256", master, password.encode(), 1, 32))


def api(path, *, method="POST", payload=None, form=None, token=None):
    headers = {
        "Accept": "application/json",
        "Device-Type": "9",
        "Bitwarden-Client-Name": "web",
        "Bitwarden-Client-Version": "2026.10.1",
    }
    data = None
    if form is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        data = urllib.parse.urlencode(form).encode()
    elif payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode()
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(API + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            text = resp.read().decode()
            return resp.status, json.loads(text) if text else None
    except urllib.error.HTTPError as err:
        text = err.read().decode()
        try:
            body = json.loads(text) if text else None
        except json.JSONDecodeError:
            body = text
        return err.code, body


def login(email, pw_hash, device, code=None):
    form = {
        "grant_type": "password",
        "username": email,
        "password": pw_hash,
        "scope": "api offline_access",
        "client_id": "web",
        "deviceType": "9",
        "deviceIdentifier": device,
        "deviceName": "interval-test",
    }
    if code:
        form["twoFactorProvider"] = "1"
        form["twoFactorToken"] = code
    return api("/identity/connect/token", form=form)


def latest_code(sink, email):
    for raw in reversed(sink.messages):
        text = raw.decode("utf-8", "replace")
        if email not in text:
            continue
        match = re.search(r"Your two-step verification code is: (\d+)", text)
        if match:
            return match.group(1)
    return None


def register(email, password, sink):
    before = len(sink.messages)
    status, body = api("/identity/accounts/register/send-verification-email", payload={"email": email, "name": "Interval"})
    token = body if status == 200 and isinstance(body, str) else None
    if token is None:
        if status not in (200, 204):
            raise SystemExit(f"verification token {status} {body}")
        for _ in range(40):
            if len(sink.messages) > before:
                break
            time.sleep(0.1)
        import quopri
        raw = b"".join(sink.messages[before:])
        text = quopri.decodestring(raw).decode("utf-8", "replace")
        match = re.search(r"token=([A-Za-z0-9_\-\.]+)", text)
        if not match:
            raise SystemExit("verification email did not include a token")
        token = urllib.parse.unquote(match.group(1))
    pw = password_hash(email, password)
    user_key = os.urandom(64)
    status, body = api("/identity/accounts/register/finish", payload={
        "email": email,
        "emailVerificationToken": token,
        "masterPasswordHash": pw,
        "masterPasswordHint": None,
        "userSymmetricKey": "2." + b64(os.urandom(16)) + "|" + b64(user_key) + "|" + b64(os.urandom(32)),
        "kdf": 0,
        "kdfIterations": 100000,
        "userAsymmetricKeys": {"publicKey": b64(os.urandom(32)), "encryptedPrivateKey": "x"},
    })
    if status != 200:
        raise SystemExit(f"register finish {status} {body}")
    return pw


def main():
    if not BIN.is_file():
        raise SystemExit(f"server binary missing: {BIN}")
    sink = Sink()
    sink.start()
    data = tempfile.mkdtemp(prefix="komboe-interval-")
    env = os.environ.copy()
    env.update({
        "DATA_FOLDER": data,
        "ROCKET_ADDRESS": "127.0.0.1",
        "ROCKET_PORT": "18081",
        "DOMAIN": "http://127.0.0.1:18081",
        "SIGNUPS_ALLOWED": "true",
        "SIGNUPS_VERIFY": "true",
        "WEB_VAULT_ENABLED": "false",
        "SMTP_HOST": "127.0.0.1",
        "SMTP_PORT": str(SINK_PORT),
        "SMTP_FROM": "donotreply@komboe.com",
        "SMTP_SECURITY": "off",
        "SMTP_FROM_NAME": "Komboe",
    })
    proc = subprocess.Popen([str(BIN)], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(80):
            try:
                urllib.request.urlopen(API + "/alive", timeout=1).read()
                break
            except Exception:
                time.sleep(0.25)
        else:
            raise SystemExit("server did not start")

        email = f"interval-{os.urandom(3).hex()}@komboe.test"
        password = "Interval-Test-Password-1"
        pw = register(email, password, sink)
        device = "device-interval-1"
        status, body = login(email, pw, device)
        if not isinstance(body, dict) or "access_token" not in body:
            raise SystemExit(f"first login without an interval should succeed: {status} {body}")
        token = body["access_token"]

        status, saved = api("/api/komboe/email-login-interval", method="PUT", token=token, payload={
            "intervalSeconds": 60,
            "masterPasswordHash": pw,
        })
        if status != 200 or saved.get("intervalSeconds") != 60:
            raise SystemExit(f"save interval {status} {saved}")

        before = len(sink.messages)
        status, challenged = login(email, pw, device)
        if not isinstance(challenged, dict) or "1" not in (challenged.get("TwoFactorProviders") or []):
            raise SystemExit(f"expected an email challenge: {status} {challenged}")
        if "access_token" in challenged:
            raise SystemExit("token issued before the email code")
        status, sent = api("/api/two-factor/send-email-login", payload={
            "email": email,
            "masterPasswordHash": pw,
            "deviceIdentifier": device,
        })
        if status != 200:
            raise SystemExit(f"send code {status} {sent}")
        if len(sink.messages) == before:
            raise SystemExit("mail sink received no code")
        code = latest_code(sink, email)
        if not code or code in json.dumps(sent):
            raise SystemExit("code missing from mail or leaked in the API body")

        status, bad = login(email, pw, device, code="00000000")
        if isinstance(bad, dict) and "access_token" in bad:
            raise SystemExit("wrong code was accepted")

        status, good = login(email, pw, device, code=code)
        if not isinstance(good, dict) or "access_token" not in good:
            raise SystemExit(f"valid code rejected: {status} {good}")

        status, again = login(email, pw, device)
        if not isinstance(again, dict) or "access_token" not in again:
            raise SystemExit(f"login inside the window was challenged: {status} {again}")

        db = Path(data) / "db.sqlite3"
        if not db.is_file():
            matches = list(Path(data).rglob("*.sqlite3"))
            if not matches:
                raise SystemExit(f"no sqlite database in {data}")
            db = matches[0]
        con = sqlite3.connect(db)
        con.execute("UPDATE komboe_email_login_trust SET verified_at = verified_at - 120")
        con.commit()
        con.close()
        status, expired = login(email, pw, device)
        if not isinstance(expired, dict) or "1" not in (expired.get("TwoFactorProviders") or []):
            raise SystemExit(f"expired trust did not challenge: {status} {expired}")
        status, replay = login(email, pw, device, code=code)
        if isinstance(replay, dict) and "access_token" in replay:
            raise SystemExit("replayed code was accepted after the window")

        unknown = f"nobody-{os.urandom(2).hex()}@komboe.test"
        mail_before = len(sink.messages)
        status, missing = login(unknown, pw, "other-device")
        if isinstance(missing, dict) and "access_token" in missing:
            raise SystemExit("unknown account received a token")
        if len(sink.messages) != mail_before:
            raise SystemExit("unknown account triggered mail")

        sink.stop()
        status, failed_send = api("/api/two-factor/send-email-login", payload={
            "email": email,
            "masterPasswordHash": pw,
            "deviceIdentifier": device,
        })
        if status == 200:
            raise SystemExit("mail failure still reported success")
        status, no_token = login(email, pw, device, code="12345678")
        if isinstance(no_token, dict) and "access_token" in no_token:
            raise SystemExit("sign-in completed after the mailer failed")
        print("EMAIL INTERVAL FLOW PASS")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        sink.stop()
        shutil.rmtree(data, ignore_errors=True)


if __name__ == "__main__":
    import urllib.error
    main()
