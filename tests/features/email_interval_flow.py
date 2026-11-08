#!/usr/bin/env python3
"""Server login exercise for the timed email code. Uses a loopback SMTP sink and a throwaway database."""
import base64
import hashlib
import hmac
import os
import re
import shutil
import socket
import sqlite3
import struct
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


def login_verifier(name: str, password: str) -> str:
    raw = hashlib.pbkdf2_hmac("sha256", password.encode(), name.encode(), 100000, 32)
    return b64(raw)


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


def login(email, pw_hash, device, code=None, trust=None, challenge=None, provider="1"):
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
    if trust:
        form["komboeDeviceTrust"] = trust
    if code:
        form["twoFactorProvider"] = provider
        form["twoFactorToken"] = code
        if challenge:
            form["komboeLoginChallenge"] = challenge
    return api("/identity/connect/token", form=form)


def totp(secret_b32, t=None):
    key = base64.b32decode(secret_b32.upper() + "=" * (-len(secret_b32) % 8))
    mac = hmac.new(key, struct.pack(">Q", int((t or time.time()) // 30)), hashlib.sha1).digest()
    offset = mac[-1] & 15
    return f"{(struct.unpack('>I', mac[offset:offset + 4])[0] & 0x7FFFFFFF) % 1000000:06d}"


def sqlite_path(data):
    db = Path(data) / "db.sqlite3"
    if db.is_file():
        return db
    matches = list(Path(data).rglob("*.sqlite3"))
    if not matches:
        raise SystemExit(f"no sqlite database in {data}")
    return matches[0]


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


def mail_disabled_does_not_lock(binary):
    """A timer cannot be turned on without mail, and an existing timer cannot trap the account."""
    data = tempfile.mkdtemp(prefix="komboe-interval-nomail-")
    log_path = Path("/tmp/komboe-nomail.log")
    env = os.environ.copy()
    env.update({
        "DATA_FOLDER": data,
        "ROCKET_ADDRESS": "127.0.0.1",
        "ROCKET_PORT": "18084",
        "DOMAIN": "http://127.0.0.1:18084",
        "SIGNUPS_ALLOWED": "true",
        "SIGNUPS_VERIFY": "false",
        "WEB_VAULT_ENABLED": "false",
        "LOGIN_RATELIMIT_MAX_BURST": "100",
        "LOGIN_RATELIMIT_SECONDS": "1",
        "SMTP_FROM": "",
    })
    for key in ("SMTP_HOST", "SMTP_PORT", "SMTP_SECURITY", "SMTP_FROM_NAME"):
        env.pop(key, None)
    log = open("/tmp/komboe-nomail.log", "w", encoding="utf-8")
    proc = subprocess.Popen([str(binary)], env=env, stdout=log, stderr=subprocess.STDOUT)
    base = "http://127.0.0.1:18084"

    def call(path, payload=None, token=None, method="POST"):
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if token:
            headers["Authorization"] = "Bearer " + token
        req = urllib.request.Request(base + path, data=json.dumps(payload).encode() if payload is not None else None, headers=headers, method=method)
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

    try:
        for _ in range(80):
            try:
                urllib.request.urlopen(base + "/alive", timeout=1).read()
                break
            except Exception:
                time.sleep(0.25)
        else:
            log.flush()
            raise SystemExit("mail-disabled server did not start\n" + log_path.read_text(encoding="utf-8", errors="replace")[-2000:])
        email = f"nomail-{os.urandom(3).hex()}@komboe.test"
        password = "Interval-Test-Password-1"
        status, body = call("/identity/accounts/register/send-verification-email", {"email": email, "name": "NoMail"})
        token = body if status == 200 and isinstance(body, str) else None
        if not token:
            raise SystemExit(f"nomail verification {status} {body}")
        pw = password_hash(email, password)
        status, body = call("/identity/accounts/register/finish", {
            "email": email,
            "emailVerificationToken": token,
            "masterPasswordHash": pw,
            "masterPasswordHint": None,
            "userSymmetricKey": "2." + b64(os.urandom(16)) + "|" + b64(os.urandom(64)) + "|" + b64(os.urandom(32)),
            "kdf": 0,
            "kdfIterations": 100000,
            "userAsymmetricKeys": {"publicKey": b64(os.urandom(32)), "encryptedPrivateKey": "x"},
        })
        if status != 200:
            raise SystemExit(f"nomail register {status} {body}")
        status, session = call("/identity/connect/token", None)
        # Password login is form-encoded. Use the shared helper against this port.
        global API
        previous = API
        API = base
        try:
            status, session = login(email, pw, "nomail-device")
        finally:
            API = previous
        if not isinstance(session, dict) or "access_token" not in session:
            raise SystemExit(f"nomail login {status} {session}")
        access = session["access_token"]
        previous = API
        API = base
        try:
            status, saved = api("/api/komboe/email-login-interval", method="PUT", token=access, payload={
                "intervalSeconds": 60,
                "masterPasswordHash": pw,
            })
            status_get, current = api("/api/komboe/email-login-interval", method="GET", token=access)
        finally:
            API = previous
        if status == 200:
            raise SystemExit(f"interval was saved while mail is disabled: {saved}")
        if not isinstance(current, dict) or current.get("intervalSeconds") not in (None, 0):
            raise SystemExit(f"rejected interval left a policy: {status_get} {current}")
        db = sqlite_path(data)
        con = sqlite3.connect(db)
        user_id = con.execute("SELECT uuid FROM users WHERE email = ?", (email,)).fetchone()[0]
        con.execute("UPDATE users SET verified_at = ? WHERE uuid = ?", ("2026-11-08 04:00:00", user_id))
        con.execute("INSERT INTO komboe_email_login_policy (user_uuid, interval_secs) VALUES (?, 60)", (user_id,))
        con.commit()
        con.close()
        previous = API
        API = base
        try:
            status, opened = login(email, pw, "nomail-device")
        finally:
            API = previous
        if isinstance(opened, dict) and "access_token" in opened:
            raise SystemExit(f"disabled mail skipped an enabled timer: {status} {opened}")
        previous = API
        API = base
        try:
            status, cleared = api("/api/komboe/email-login-interval", method="PUT", token=access, payload={
                "intervalSeconds": 0,
                "masterPasswordHash": pw,
            })
            if status != 200 or not (isinstance(cleared, dict) and cleared.get("never") is True):
                raise SystemExit(f"authenticated timer disable failed: {status} {cleared}")
            status, after = login(email, pw, "nomail-device")
        finally:
            API = previous
        if not isinstance(after, dict) or "access_token" not in after:
            raise SystemExit(f"login after explicit timer disable failed: {status} {after}")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        shutil.rmtree(data, ignore_errors=True)


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
        "LOGIN_RATELIMIT_MAX_BURST": "100",
        "LOGIN_RATELIMIT_SECONDS": "1",
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

        status, named = api("/api/komboe/login-name", method="PUT", token=token, payload={
            "name": "intervalname",
            "masterPasswordHash": pw,
            "loginVerifier": login_verifier("intervalname", password),
        })
        if status != 200:
            raise SystemExit(f"login name {status} {named}")
        db = sqlite_path(data)
        con = sqlite3.connect(db)
        con.execute("UPDATE users SET client_kdf_iter = 123456 WHERE email = ?", (email,))
        con.commit()
        con.close()
        status, leaked = api("/identity/accounts/prelogin", payload={"email": "intervalname"})
        blob = json.dumps(leaked).lower()
        if email.lower() in blob or (isinstance(leaked, dict) and leaked.get("kdfIterations") == 123456):
            raise SystemExit(f"prelogin disclosed the account: {status} {leaked}")
        if isinstance(leaked, dict) and "email" in leaked:
            raise SystemExit(f"prelogin returned an email field: {leaked}")
        status, wrong_name = api("/identity/accounts/login-name/resolve", payload={
            "name": "intervalname",
            "loginVerifier": login_verifier("intervalname", "not-the-password"),
        })
        wrong_blob = json.dumps(wrong_name).lower()
        if email.lower() in wrong_blob or (isinstance(wrong_name, dict) and wrong_name.get("kdfIterations") == 123456):
            raise SystemExit(f"wrong verifier disclosed the account: {status} {wrong_name}")
        status, resolved = api("/identity/accounts/login-name/resolve", payload={
            "name": "intervalname",
            "loginVerifier": login_verifier("intervalname", password),
        })
        if status != 200 or not isinstance(resolved, dict) or resolved.get("email", "").lower() != email.lower():
            raise SystemExit(f"login name proof failed: {status} {resolved}")
        if resolved.get("kdfIterations") != 123456:
            raise SystemExit(f"login name proof hid the real KDF: {resolved}")
        if isinstance(leaked, dict) and "email" in leaked:
            raise SystemExit(f"prelogin returned an email field: {leaked}")

        before = len(sink.messages)
        status, challenged = login(email, pw, device)
        if not isinstance(challenged, dict) or "1" not in (challenged.get("TwoFactorProviders") or []):
            raise SystemExit(f"expected an email challenge: {status} {challenged}")
        if "access_token" in challenged or not challenged.get("KomboeLoginChallenge"):
            raise SystemExit(f"challenge nonce missing: {status} {challenged}")
        challenge = challenged["KomboeLoginChallenge"]
        status, copied = login(email, pw, device, trust="copied-public-device-id")
        if isinstance(copied, dict) and "access_token" in copied:
            raise SystemExit("a copied device id skipped the email code")
        status, bare = api("/api/two-factor/send-email-login", payload={
            "email": email,
            "masterPasswordHash": pw,
            "deviceIdentifier": device,
        })
        if status == 200:
            raise SystemExit("a device id alone sent a code")
        status, sent = api("/api/two-factor/send-email-login", payload={
            "email": email,
            "masterPasswordHash": pw,
            "deviceIdentifier": device,
            "komboeLoginChallenge": challenge,
        })
        if status != 200:
            raise SystemExit(f"send code {status} {sent}")
        status, resent = api("/api/two-factor/send-email-login", payload={
            "email": email,
            "masterPasswordHash": pw,
            "komboeLoginChallenge": challenge,
        })
        if status == 200:
            raise SystemExit("a resend inside the gap was accepted")
        if len(sink.messages) == before:
            raise SystemExit("mail sink received no code")
        code = latest_code(sink, email)
        if not code or code in json.dumps(sent):
            raise SystemExit("code missing from mail or leaked in the API body")

        status, wrong_challenge = login(email, pw, device, code=code, challenge="not-this-login")
        if isinstance(wrong_challenge, dict) and "access_token" in wrong_challenge:
            raise SystemExit("a code was accepted for a different challenge")
        status, bad = login(email, pw, device, code="00000000", challenge=challenge)
        if isinstance(bad, dict) and "access_token" in bad:
            raise SystemExit("wrong code was accepted")
        status, good = login(email, pw, device, code=code, challenge=challenge)
        if not isinstance(good, dict) or "access_token" not in good or not good.get("KomboeDeviceTrust"):
            raise SystemExit(f"valid code rejected: {status} {good}")
        trust = good["KomboeDeviceTrust"]

        status, device_only = login(email, pw, device)
        if isinstance(device_only, dict) and "access_token" in device_only:
            raise SystemExit("password plus the public device id skipped the timer")
        status, again = login(email, pw, "different-device", trust=trust)
        if not isinstance(again, dict) or "access_token" not in again:
            raise SystemExit(f"server trust token was not accepted: {status} {again}")
        if "KomboeDeviceTrust" in again:
            raise SystemExit("an in-window login issued a replacement token and would drop the current one")

        con = sqlite3.connect(db)
        con.execute("UPDATE komboe_email_trust_tokens SET verified_at = verified_at - 50")
        con.commit()
        status, still = login(email, pw, "another-device", trust=trust)
        if not isinstance(still, dict) or "access_token" not in still:
            raise SystemExit(f"trust inside the window was dropped: {status} {still}")
        stamped = con.execute("SELECT verified_at FROM komboe_email_trust_tokens").fetchone()[0]
        con.execute("UPDATE komboe_email_trust_tokens SET verified_at = ?", (stamped,))
        status, wrong = login(email, pw, "another-device", trust="not-the-token")
        moved = con.execute("SELECT verified_at FROM komboe_email_trust_tokens").fetchone()[0]
        con.execute("UPDATE komboe_email_trust_tokens SET verified_at = verified_at - 120")
        con.commit()
        con.close()
        if moved != stamped:
            raise SystemExit("a failed login moved the trust window")
        status, expired = login(email, pw, device, trust=trust)
        if not isinstance(expired, dict) or "1" not in (expired.get("TwoFactorProviders") or []):
            raise SystemExit(f"expired trust did not challenge: {status} {expired}")
        status, replay = login(email, pw, device, code=code, challenge=challenge)
        if isinstance(replay, dict) and "access_token" in replay:
            raise SystemExit("replayed code was accepted after the window")

        status, cleared = api("/api/komboe/email-login-trust/clear", token=good["access_token"], payload={"token": trust})
        if status not in (200, 204):
            raise SystemExit(f"revoke {status} {cleared}")
        con = sqlite3.connect(db)
        con.execute("UPDATE komboe_email_trust_tokens SET verified_at = ?", (int(time.time()),))
        con.commit()
        con.close()
        status, revoked = login(email, pw, device, trust=trust)
        if isinstance(revoked, dict) and "access_token" in revoked:
            raise SystemExit("a revoked trust token skipped the email code")

        unknown = f"nobody-{os.urandom(2).hex()}@komboe.test"
        mail_before = len(sink.messages)
        status, missing = login(unknown, pw, "other-device")
        if isinstance(missing, dict) and "access_token" in missing:
            raise SystemExit("unknown account received a token")
        if len(sink.messages) != mail_before:
            raise SystemExit("unknown account triggered mail")

        status, raced = login(email, pw, "race-device")
        race_id = raced.get("KomboeLoginChallenge") if isinstance(raced, dict) else None
        status, race_sent = api("/api/two-factor/send-email-login", payload={
            "email": email,
            "masterPasswordHash": pw,
            "komboeLoginChallenge": race_id or "",
        })
        if status != 200:
            raise SystemExit(f"race send {status} {race_sent}")
        race_code = latest_code(sink, email)
        race_results = []

        def submit_race():
            race_results.append(login(email, pw, "race-device", code=race_code, challenge=race_id))

        threads = [threading.Thread(target=submit_race), threading.Thread(target=submit_race)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        wins = [item for item in race_results if isinstance(item[1], dict) and "access_token" in item[1]]
        if len(wins) != 1:
            raise SystemExit(f"the same code was accepted {len(wins)} times: {race_results}")

        email_b = f"other-{os.urandom(3).hex()}@komboe.test"
        pw_b = register(email_b, password, sink)
        status, session_b = login(email_b, pw_b, "b-device")
        if not isinstance(session_b, dict) or "access_token" not in session_b:
            raise SystemExit(f"second account login {status} {session_b}")
        status, saved_b = api("/api/komboe/email-login-interval", method="PUT", token=session_b["access_token"], payload={
            "intervalSeconds": 60,
            "masterPasswordHash": pw_b,
        })
        if status != 200:
            raise SystemExit(f"second interval {status} {saved_b}")
        status, scoped = login(email_b, pw_b, "b-other", trust=trust)
        if isinstance(scoped, dict) and "access_token" in scoped:
            raise SystemExit("a trust token for one account unlocked another")

        sink.stop()
        status, fresh = login(email, pw, "mail-fail-device")
        fresh_challenge = fresh.get("KomboeLoginChallenge") if isinstance(fresh, dict) else None
        status, failed_send = api("/api/two-factor/send-email-login", payload={
            "email": email,
            "masterPasswordHash": pw,
            "komboeLoginChallenge": fresh_challenge or "",
        })
        if status == 200:
            raise SystemExit("mail failure still reported success")
        status, no_token = login(email, pw, device, code="12345678", challenge=fresh_challenge)
        if isinstance(no_token, dict) and "access_token" in no_token:
            raise SystemExit("sign-in completed after the mailer failed")

        status, key_body = api("/api/two-factor/get-authenticator", method="POST", token=token, payload={"masterPasswordHash": pw})
        if status != 200 or not isinstance(key_body, dict) or not key_body.get("key"):
            raise SystemExit(f"authenticator key {status} {key_body}")
        secret = key_body["key"]
        status, enabled = api("/api/two-factor/authenticator", method="PUT", token=token, payload={
            "key": secret,
            "token": totp(secret),
            "masterPasswordHash": pw,
        })
        if status != 200:
            raise SystemExit(f"enable authenticator {status} {enabled}")
        status, skipped = login(email, pw, device, trust=trust)
        providers = (skipped or {}).get("TwoFactorProviders") if isinstance(skipped, dict) else None
        if isinstance(skipped, dict) and "access_token" in skipped:
            raise SystemExit("a trust token skipped authenticator 2FA")
        if not providers or "0" not in providers:
            raise SystemExit(f"authenticator was not required: {status} {skipped}")
        status, with_totp = login(email, pw, device, code=totp(secret, time.time() + 30), provider="0")
        if not isinstance(with_totp, dict) or "access_token" not in with_totp:
            raise SystemExit(f"authenticator code rejected: {status} {with_totp}")
        mail_disabled_does_not_lock(BIN)
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
