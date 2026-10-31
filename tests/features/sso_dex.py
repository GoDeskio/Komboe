#!/usr/bin/env python3
"""OIDC SSO against a real Dex process (no in-product fake IdP).

Drives Vaultwarden's authorization-code + PKCE flow the way the web client does:
prevalidate, /identity/connect/authorize, Dex password login, callback, token.
Keycloak browser E2E is intentionally not run here.
"""
import base64
import hashlib
import http.cookiejar
import os
import re
import socket
import sqlite3
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from html import unescape

import importlib.util

spec = importlib.util.spec_from_file_location("ft", os.path.join(os.path.dirname(__file__), "run.py"))
ft = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ft)

BIN = os.environ.get("KOMBOE_BIN", "/workspace/server/upstream/target/release/vaultwarden")
DEX = os.environ.get("KOMBOE_DEX_BIN", "/tmp/dex-bin/dex")
VW = "http://127.0.0.1:18090"
DEX_ISSUER = "http://127.0.0.1:5556/dex"
EMAIL = "ada@komboe.test"
PASSWORD = "Sso-Test-Pass"
# bcrypt of PASSWORD, cost 10. Test credential only.
BCRYPT = "$2a$10$7ZpjXHhm0NF8njcnK4q41eeKmEbOERQXVBNOROnzvEwCumnkJH0hu"
CLIENT_SECRET = "komboe-sso-secret"


def wait_port(port, timeout=40):
    end = time.time() + timeout
    while time.time() < end:
        s = socket.socket()
        s.settimeout(0.3)
        try:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return
        finally:
            s.close()
        time.sleep(0.2)
    raise SystemExit(f"port {port} did not open")


def wait_http(url, timeout=30):
    end = time.time() + timeout
    while time.time() < end:
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if 200 <= r.status < 300:
                    return
        except Exception:
            time.sleep(0.3)
    raise SystemExit(f"not ready: {url}")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        err = urllib.error.HTTPError(req.full_url, code, msg, headers, fp)
        err.komboe_next = urllib.parse.urljoin(req.full_url, newurl)
        raise err


def step(opener, url, method="GET", data=None, headers=None):
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with opener.open(req, timeout=20) as resp:
            return resp.status, resp.headers, resp.read(), resp.geturl()
    except urllib.error.HTTPError as e:
        nxt = getattr(e, "komboe_next", None)
        if nxt:
            return e.code, e.headers, b"", nxt
        return e.code, e.headers, e.read(), url


def form_action(body, page_url):
    m = re.search(br'<form[^>]*action="([^"]*)"', body, re.I)
    if not m:
        return page_url
    return urllib.parse.urljoin(page_url, unescape(m.group(1).decode()))


def hidden(body, name):
    m = re.search(br'name="' + name.encode() + br'"[^>]*value="([^"]*)"', body)
    if not m:
        m = re.search(br'value="([^"]*)"[^>]*name="' + name.encode() + br'"', body)
    return unescape(m.group(1).decode()) if m else None


def is_connector(url):
    return urllib.parse.urlparse(url).path.endswith("/sso-connector.html")


def login_at_dex(opener, start_url):
    url, method, data = start_url, "GET", None
    for _ in range(16):
        code, _headers, body, final = step(opener, url, method, data)
        if is_connector(final) or is_connector(url):
            return final if is_connector(final) else url
        if code in (301, 302, 303, 307, 308):
            url, method, data = final, "GET", None
            continue
        if code != 200:
            raise SystemExit(f"IdP HTTP {code} at {url}: {body[:400]!r}")
        if b'name="login"' in body and b'name="password"' in body:
            url = form_action(body, final)
            data = urllib.parse.urlencode({"login": EMAIL, "password": PASSWORD}).encode()
            method = "POST"
            continue
        if b'name="approval"' in body:
            url = form_action(body, final)
            fields = {"approval": "approve"}
            req = hidden(body, "req")
            if req:
                fields["req"] = req
            data = urllib.parse.urlencode(fields).encode()
            method = "POST"
            continue
        raise SystemExit(f"unexpected IdP page at {final}: {body[:500]!r}")
    raise SystemExit("IdP redirect loop")


def main():
    if not os.path.isfile(BIN):
        raise SystemExit(f"vaultwarden binary missing: {BIN}")
    if not os.path.isfile(DEX):
        raise SystemExit(f"dex binary missing: {DEX}")
    folder = "/tmp/komboe-sso"
    if os.path.isdir(folder):
        import shutil
        shutil.rmtree(folder)
    os.makedirs(folder, exist_ok=True)
    dex_cfg = "/tmp/komboe-sso-dex.yaml"
    with open(dex_cfg, "w") as f:
        f.write(f"""issuer: {DEX_ISSUER}
storage:
  type: memory
web:
  http: 127.0.0.1:5556
telemetry:
  http: 127.0.0.1:5558
oauth2:
  skipApprovalScreen: true
staticClients:
- id: komboe
  redirectURIs:
  - '{VW}/identity/connect/oidc-signin'
  name: Komboe
  secret: {CLIENT_SECRET}
enablePasswordDB: true
staticPasswords:
- email: "{EMAIL}"
  hash: "{BCRYPT}"
  username: ada
  userID: "08a8684b-db88-4b73-90a9-3cd1661f5466"
  emailVerified: true
""")
    procs = []
    try:
        dex_log = open(folder + "-dex.log", "w")
        procs.append(subprocess.Popen([DEX, "serve", dex_cfg], stdout=dex_log, stderr=subprocess.STDOUT))
        wait_http(DEX_ISSUER + "/.well-known/openid-configuration")
        env = os.environ.copy()
        env.update({
            "DATA_FOLDER": folder,
            "ROCKET_PORT": "18090",
            "ROCKET_ADDRESS": "127.0.0.1",
            "DOMAIN": VW,
            "SIGNUPS_ALLOWED": "true",
            "WEB_VAULT_ENABLED": "false",
            "SSO_ENABLED": "true",
            "SSO_AUTHORITY": DEX_ISSUER,
            "SSO_CLIENT_ID": "komboe",
            "SSO_CLIENT_SECRET": CLIENT_SECRET,
            "SSO_SCOPES": "email profile",
            "SSO_PKCE": "true",
            "SSO_SIGNUPS_ALLOWED": "true",
            "SSO_ALLOW_UNKNOWN_EMAIL_VERIFICATION": "true",
            "LOGIN_RATELIMIT_MAX_BURST": "1000",
        })
        vw_log = open(folder + "-vw.log", "w")
        procs.append(subprocess.Popen([BIN], env=env, stdout=vw_log, stderr=subprocess.STDOUT))
        wait_port(18090)
        time.sleep(0.4)

        pre = ft.http("GET", "/identity/sso/prevalidate", base=VW)
        assert pre.get("token"), pre

        verifier = base64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode()
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        state = uuid.uuid4().hex
        qs = urllib.parse.urlencode({
            "client_id": "web",
            "redirect_uri": VW + "/sso-connector.html",
            "response_type": "code",
            "scope": "api offline_access",
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        })
        jar = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar), NoRedirect)
        landed = login_at_dex(opener, VW + "/identity/connect/authorize?" + qs)
        q = urllib.parse.parse_qs(urllib.parse.urlparse(landed).query)
        code = q["code"][0]
        assert q["state"][0] == state, q
        assert "offline_access" in q.get("scope", [""])[0]

        login = ft.http("POST", "/identity/connect/token", form={
            "grant_type": "authorization_code",
            "client_id": "web",
            "code": code,
            "code_verifier": verifier,
            "scope": "api offline_access",
            "deviceType": "10",
            "deviceIdentifier": uuid.uuid4().hex,
            "deviceName": "sso-dex",
        }, base=VW)
        assert login.get("access_token"), login
        profile = ft.http("GET", "/api/accounts/profile", token=login["access_token"], base=VW)
        assert profile["email"] == EMAIL, profile

        db = sqlite3.connect(os.path.join(folder, "db.sqlite3"))
        row = db.execute("select password_hash, private_key, email from users where email = ?", (EMAIL,)).fetchone()
        assert row and row[2] == EMAIL, row
        assert not row[0], "SSO must not store a master-password hash"
        assert row[1] is None, "SSO identity login must not escrow a user key"
        blob = open(os.path.join(folder, "db.sqlite3"), "rb").read()
        assert PASSWORD.encode() not in blob
        assert CLIENT_SECRET.encode() not in blob
        print("SSO DEX PASS")
    finally:
        for proc in procs:
            proc.terminate()
        for proc in procs:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    main()
