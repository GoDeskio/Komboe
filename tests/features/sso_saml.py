#!/usr/bin/env python3
"""SAML 2.0 SSO against a real pysaml2 IdP (xmlsec1-signed assertions).

Flow: prevalidate -> /identity/connect/authorize (SAML AuthnRequest, HTTP-Redirect) -> IdP login ->
signed Response POSTed to /identity/connect/saml-acs -> /identity/connect/saml-signin (binding cookie)
-> client redirect with code -> /identity/connect/token (PKCE).
Negative cases: tampered, unsigned, wrong signing key, wrong audience (validly signed), replay,
missing binding cookie. Checks that no vault key / private key / password hash is stored.
Needs: venv with pysaml2 (KOMBOE_SAML_PY), xmlsec1.
"""
import base64
import hashlib
import http.cookiejar
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
import uuid
import zlib

import importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "e2e", "saml_idp"))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


ft = _load("ft", os.path.join(HERE, "run.py"))
dex = _load("sso_dex", os.path.join(HERE, "sso_dex.py"))
import idp as samlidp  # noqa: E402

BIN = os.environ.get("KOMBOE_BIN", "/workspace/komboe/server/upstream/target/release/vaultwarden")
PORT, IDP_PORT = 18091, 18092
VW = f"http://127.0.0.1:{PORT}"
EMAIL, PASSWORD, NAME = "grace@komboe.test", "Saml-Test-Pass", "Grace Hopper"
SP_ENTITY = VW + "/identity/saml/metadata"
ACS = VW + "/identity/connect/saml-acs"


def pkce():
    v = base64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode()
    c = base64.urlsafe_b64encode(hashlib.sha256(v.encode()).digest()).rstrip(b"=").decode()
    return v, c


def opener():
    jar = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar), dex.NoRedirect), jar


def start_authorize(op):
    v, c = pkce()
    state = uuid.uuid4().hex
    qs = urllib.parse.urlencode({"client_id": "web", "redirect_uri": VW + "/sso-connector.html",
                                 "response_type": "code", "scope": "api offline_access", "state": state,
                                 "code_challenge": c, "code_challenge_method": "S256"})
    code, _h, body, nxt = dex.step(op, VW + "/identity/connect/authorize?" + qs)
    assert code in (302, 303, 307), (code, body[:300])
    u = urllib.parse.urlparse(nxt)
    assert nxt.startswith(f"http://127.0.0.1:{IDP_PORT}/sso/redirect"), nxt
    q = urllib.parse.parse_qs(u.query)
    req_xml = zlib.decompress(base64.b64decode(q["SAMLRequest"][0]), -15).decode()
    req_id = re.search(r'\bID="([^"]+)"', req_xml).group(1)
    assert 'AssertionConsumerServiceURL="' + ACS + '"' in req_xml, req_xml
    return dict(verifier=v, state=state, relay=q["RelayState"][0], req_id=req_id, idp_url=nxt)


def post_acs(op, b64, relay):
    data = urllib.parse.urlencode({"SAMLResponse": b64, "RelayState": relay}).encode()
    return dex.step(op, ACS, "POST", data, {"Content-Type": "application/x-www-form-urlencoded"})


def finish(op, acs_result, flow):
    code, _h, body, nxt = acs_result
    assert code == 303 and "/identity/connect/saml-signin" in nxt, (code, body[:400], nxt)
    code, _h, body, landed = dex.step(op, nxt)
    assert code in (302, 303, 307) and dex.is_connector(landed), (code, body[:400], landed)
    q = urllib.parse.parse_qs(urllib.parse.urlparse(landed).query)
    assert q["state"][0] == flow["state"], q
    return q["code"][0]


def token(code, verifier):
    return ft.http("POST", "/identity/connect/token", form={
        "grant_type": "authorization_code", "client_id": "web", "code": code, "code_verifier": verifier,
        "scope": "api offline_access", "deviceType": "10", "deviceIdentifier": uuid.uuid4().hex,
        "deviceName": "sso-saml"}, base=VW)


def expect_reject(name, result):
    code = result[0]
    if code >= 400:
        print("    server said:", result[2][:160].decode(errors="replace").replace("\n", " "))
    assert code >= 400, f"{name}: expected rejection, got {code} {result[3]}"
    print(f"  reject ok: {name} ({code})")


def b64(xml):
    return base64.b64encode(xml.encode()).decode()


def main():
    folder = tempfile.mkdtemp(prefix="komboe-saml-")
    keys = os.path.join(folder, "keys")
    os.makedirs(keys)
    key, crt = samlidp.make_keypair(keys, "idp")
    bad_key, bad_crt = samlidp.make_keypair(keys, "rogue")
    idp_base = f"http://127.0.0.1:{IDP_PORT}"
    env = os.environ.copy()
    env.update({
        "DATA_FOLDER": os.path.join(folder, "data"), "ROCKET_PORT": str(PORT), "ROCKET_ADDRESS": "127.0.0.1",
        "DOMAIN": VW, "SIGNUPS_ALLOWED": "true", "WEB_VAULT_ENABLED": "false",
        "SSO_ENABLED": "true", "SSO_SAML_ENABLED": "true", "SSO_SAML_IDP_ENTITY_ID": idp_base + "/metadata",
        "SSO_SAML_IDP_SSO_URL": idp_base + "/sso/redirect", "SSO_SAML_IDP_CERT": crt,
        "SSO_SAML_EMAIL_VERIFIED": "true", "SSO_SIGNUPS_ALLOWED": "true", "SSO_PKCE": "true",
        "LOGIN_RATELIMIT_MAX_BURST": "1000",
    })
    os.makedirs(env["DATA_FOLDER"])
    log = open(os.path.join(folder, "vw.log"), "w")
    vw = subprocess.Popen([BIN], env=env, stdout=log, stderr=subprocess.STDOUT)
    idp = None
    try:
        dex.wait_port(PORT)
        time.sleep(0.4)
        md = urllib.request.urlopen(VW + "/identity/saml/metadata", timeout=10).read().decode()
        assert SP_ENTITY in md and ACS in md, md
        md_file = os.path.join(folder, "sp.xml")
        open(md_file, "w").write(md)
        idp = samlidp.IdP(IDP_PORT, key, crt, md_file, {EMAIL: {"password": PASSWORD, "name": NAME}}).start()
        rogue = samlidp.build_server(idp_base, bad_key, bad_crt, md_file)

        assert ft.http("GET", "/identity/sso/prevalidate", base=VW).get("token")

        # --- happy path through the real IdP login form ---
        op, _ = opener()
        flow = start_authorize(op)
        code, _h, body, url = dex.step(op, flow["idp_url"])
        assert code == 200 and b'name="password"' in body
        data = urllib.parse.urlencode({"key": dex.hidden(body, "key"), "username": EMAIL, "password": PASSWORD}).encode()
        code, _h, body, _u = dex.step(op, idp_base + "/login", "POST", data)
        assert code == 200, body[:300]
        assert dex.form_action(body, url) == ACS
        saml_b64, relay = dex.hidden(body, "SAMLResponse"), dex.hidden(body, "RelayState")
        xml = base64.b64decode(saml_b64).decode()
        assert "<ds:Signature" in xml or ":Signature" in xml, "IdP must sign"
        good = post_acs(op, saml_b64, relay)
        c = finish(op, good, flow)
        login = token(c, flow["verifier"])
        assert login.get("access_token"), login
        prof = ft.http("GET", "/api/accounts/profile", token=login["access_token"], base=VW)
        assert prof["email"] == EMAIL, prof
        print("  happy path ok: signed assertion verified, token issued")

        # replay of the same signed response against the same (consumed) state
        expect_reject("replay same state", post_acs(op, saml_b64, relay))
        # replay against a fresh state (InResponseTo mismatch)
        op2, _ = opener()
        f2 = start_authorize(op2)
        expect_reject("replay new state", post_acs(op2, saml_b64, f2["relay"]))
        # the code must not be redeemable twice
        try:
            token(c, flow["verifier"]); raise AssertionError("code reuse accepted")
        except ft.HTTPErr if hasattr(ft, "HTTPErr") else Exception as e:
            assert "code reuse accepted" not in str(e), e
        print("  reject ok: code reuse")

        def fresh():
            o, _ = opener()
            return o, start_authorize(o)

        def mk(server, f, email=EMAIL, sign=True):
            return samlidp.signed_response(server, f["req_id"], ACS, SP_ENTITY, email, NAME, sign=sign)

        o, f = fresh()
        x = mk(idp.server, f).replace(EMAIL, "mallory@komboe.test")
        expect_reject("tampered (email changed after signing)", post_acs(o, b64(x), f["relay"]))
        o, f = fresh()
        expect_reject("unsigned assertion", post_acs(o, b64(mk(idp.server, f, sign=False)), f["relay"]))
        o, f = fresh()
        expect_reject("signed by untrusted key", post_acs(o, b64(mk(rogue, f)), f["relay"]))
        o, f = fresh()
        x = re.sub(r"(<(?:\w+:)?Audience>)[^<]*(</)", r"\1https://evil.example/sp\2", mk(idp.server, f))
        assert "evil.example" in x, "audience element not found"
        x = samlidp.resign(x, key)
        expect_reject("wrong audience (validly signed)", post_acs(o, b64(x), f["relay"]))
        # sanity: resign path itself yields an accepted assertion when audience is right
        o, f = fresh()
        ok = post_acs(o, b64(samlidp.resign(mk(idp.server, f), key)), f["relay"])
        finish(o, ok, f)
        # missing binding cookie: valid ACS, then saml-signin from a cookieless client
        o, f = fresh()
        r = post_acs(o, b64(mk(idp.server, f)), f["relay"])
        assert r[0] == 303, r[:2]
        bare = urllib.request.build_opener(dex.NoRedirect)
        code, _h, body, landed = dex.step(bare, r[3])
        assert code >= 400 or not dex.is_connector(landed), (code, landed)
        print(f"  reject ok: missing binding cookie ({code})")

        # --- no key material / secrets stored ---
        db = sqlite3.connect(os.path.join(env["DATA_FOLDER"], "db.sqlite3"))
        row = db.execute("select password_hash, private_key, akey from users where email=?", (EMAIL,)).fetchone()
        assert row and not row[0] and row[1] is None and not row[2], "SSO must not store hash/private key/vault key"
        assert db.execute("select count(*) from users where email='mallory@komboe.test'").fetchone()[0] == 0
        ident = db.execute("select identifier from sso_users").fetchall()
        assert any(i[0].startswith("saml:") for i in ident), ident
        db.close()
        blob = b"".join(open(os.path.join(env["DATA_FOLDER"], n), "rb").read() for n in ("db.sqlite3", "db.sqlite3-wal")
                        if os.path.exists(os.path.join(env["DATA_FOLDER"], n)))
        assert PASSWORD.encode() not in blob
        assert open(key, "rb").read().split(b"\n")[1] not in blob
        print("SSO SAML PASS")
    finally:
        if idp:
            idp.stop()
        vw.terminate()
        try:
            vw.wait(timeout=5)
        except subprocess.TimeoutExpired:
            vw.kill()
        if os.environ.get("KEEP") != "1":
            shutil.rmtree(folder, ignore_errors=True)
        else:
            print("kept", folder)


if __name__ == "__main__":
    main()
