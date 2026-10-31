#!/usr/bin/env python3
"""SAML hardening: signed AuthnRequests, encrypted assertions, single logout (pysaml2 IdP + xmlsec1).

Server runs with SSO_SAML_SP_KEY/CERT, SSO_SAML_IDP_SLO_URL and SSO_SAML_REQUIRE_ENCRYPTED_ASSERTIONS.
Checks: metadata advertises keys/SLO; AuthnRequest + logout redirects carry a valid RSA-SHA256 signature by
the SP key; encrypted+signed assertion logs in; plaintext, unsigned-encrypted and rogue-signed rejected;
IdP-initiated LogoutRequest (signed) kills refresh/access tokens; unsigned/rogue LogoutRequest rejected;
SP-initiated logout returns a signed LogoutRequest and ends sessions; signed LogoutResponse accepted.
Still zero-knowledge: no vault key, private key or password hash stored.
"""
import base64
import os
import re
import shutil
import sqlite3
import subprocess
import tempfile
import time
import urllib.parse
import uuid
import zlib
from datetime import datetime, timezone, timedelta

import sso_saml as base  # reuses helpers (same folder)

samlidp, dex, ft = base.samlidp, base.dex, base.ft
import saml2.sigver  # noqa: E402

# pysaml2 defaults to 3DES; real IdPs (and Komboe) use AES. Keep RSA-OAEP key transport.
saml2.sigver.pre_encryption_part.__kwdefaults__["msg_enc"] = "http://www.w3.org/2001/04/xmlenc#aes256-cbc"
_enc = saml2.sigver.SecurityContext.encrypt_assertion
saml2.sigver.SecurityContext.encrypt_assertion = lambda self, st, k, t, key_type=None, node_xpath=None: _enc(
    self, st, k, t, key_type="aes-256", node_xpath=node_xpath)
PORT, IDP_PORT = 18093, 18094
VW = f"http://127.0.0.1:{PORT}"
base.PORT, base.IDP_PORT, base.VW = PORT, IDP_PORT, VW
base.SP_ENTITY, base.ACS = VW + "/identity/saml/metadata", VW + "/identity/connect/saml-acs"
SLO = VW + "/identity/connect/saml-slo"
XMLSEC1 = os.environ.get("XMLSEC1", "/usr/bin/xmlsec1")
NS = 'xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol" xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion"'


def verify_redirect_sig(url, sp_crt, folder):
    """Check the HTTP-Redirect binding signature over the raw query, as the IdP would."""
    raw = urllib.parse.urlparse(url).query
    parts = dict(p.split("=", 1) for p in raw.split("&"))
    msg = "SAMLRequest" if "SAMLRequest" in parts else "SAMLResponse"
    signed = "&".join(f"{k}={parts[k]}" for k in (msg, "RelayState", "SigAlg") if k in parts)
    assert urllib.parse.unquote_plus(parts["SigAlg"]) == "http://www.w3.org/2001/04/xmldsig-more#rsa-sha256"
    sig = base64.b64decode(urllib.parse.unquote_plus(parts["Signature"]))
    d, s, pub = (os.path.join(folder, n) for n in ("d.bin", "s.bin", "pub.pem"))
    open(d, "w").write(signed); open(s, "wb").write(sig)
    pk = subprocess.run(["openssl", "x509", "-in", sp_crt, "-pubkey", "-noout"], check=True, capture_output=True).stdout
    open(pub, "wb").write(pk)
    r = subprocess.run(["openssl", "dgst", "-sha256", "-verify", pub, "-signature", s, d], capture_output=True)
    assert r.returncode == 0, ("bad redirect signature", r.stdout, r.stderr)
    return zlib.decompress(base64.b64decode(urllib.parse.unquote_plus(parts[msg])), -15).decode()


def sign_msg(xml, key, local):
    """Insert an enveloped signature template after Issuer and sign with xmlsec1."""
    rid = re.search(r'\bID="([^"]+)"', xml).group(1)
    tpl = ('<ds:Signature xmlns:ds="http://www.w3.org/2000/09/xmldsig#"><ds:SignedInfo>'
           '<ds:CanonicalizationMethod Algorithm="http://www.w3.org/2001/10/xml-exc-c14n#"/>'
           '<ds:SignatureMethod Algorithm="http://www.w3.org/2001/04/xmldsig-more#rsa-sha256"/>'
           f'<ds:Reference URI="#{rid}"><ds:Transforms>'
           '<ds:Transform Algorithm="http://www.w3.org/2000/09/xmldsig#enveloped-signature"/>'
           '<ds:Transform Algorithm="http://www.w3.org/2001/10/xml-exc-c14n#"/></ds:Transforms>'
           '<ds:DigestMethod Algorithm="http://www.w3.org/2001/04/xmlenc#sha256"/><ds:DigestValue/></ds:Reference>'
           '</ds:SignedInfo><ds:SignatureValue/></ds:Signature>')
    xml = xml.replace("</saml:Issuer>", "</saml:Issuer>" + tpl, 1)
    with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False) as f:
        f.write(xml)
    out = subprocess.run([XMLSEC1, "--sign", "--privkey-pem", key, "--id-attr:ID",
                          f"urn:oasis:names:tc:SAML:2.0:protocol:{local}", f.name],
                         check=True, capture_output=True, text=True).stdout
    os.unlink(f.name)
    return out


def now(delta=0):
    return (datetime.now(timezone.utc) + timedelta(seconds=delta)).strftime("%Y-%m-%dT%H:%M:%SZ")


def logout_request(issuer, name_id):
    return (f'<samlp:LogoutRequest {NS} ID="_lr{uuid.uuid4().hex}" Version="2.0" IssueInstant="{now()}" '
            f'Destination="{SLO}" NotOnOrAfter="{now(300)}"><saml:Issuer>{issuer}</saml:Issuer>'
            f'<saml:NameID Format="urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress">{name_id}</saml:NameID>'
            '</samlp:LogoutRequest>')


def logout_response(issuer, irt):
    return (f'<samlp:LogoutResponse {NS} ID="_ls{uuid.uuid4().hex}" Version="2.0" IssueInstant="{now()}" '
            f'Destination="{SLO}" InResponseTo="{irt}"><saml:Issuer>{issuer}</saml:Issuer><samlp:Status>'
            '<samlp:StatusCode Value="urn:oasis:names:tc:SAML:2.0:status:Success"/></samlp:Status>'
            '</samlp:LogoutResponse>')


def post_slo(op, field, xml):
    data = urllib.parse.urlencode({field: base64.b64encode(xml.encode()).decode(), "RelayState": "rs1"}).encode()
    return dex.step(op, SLO, "POST", data, {"Content-Type": "application/x-www-form-urlencoded"})


def refresh(rt):
    return ft.http("POST", "/identity/connect/token", form={"grant_type": "refresh_token", "client_id": "web",
                                                             "refresh_token": rt}, base=VW)


def assert_dead(login):
    try:
        refresh(login["refresh_token"]); raise AssertionError("refresh token still valid")
    except ft.HTTPErr:
        pass
    try:
        ft.http("GET", "/api/accounts/profile", token=login["access_token"], base=VW)
        raise AssertionError("access token still valid")
    except ft.HTTPErr:
        pass


def main():
    folder = tempfile.mkdtemp(prefix="komboe-samlh-")
    keys = os.path.join(folder, "keys"); os.makedirs(keys)
    key, crt = samlidp.make_keypair(keys, "idp")
    bad_key, bad_crt = samlidp.make_keypair(keys, "rogue")
    sp_key, sp_crt = samlidp.make_keypair(keys, "sp")
    idp_base = f"http://127.0.0.1:{IDP_PORT}"
    idp_entity = idp_base + "/metadata"
    env = os.environ.copy()
    env.update({
        "DATA_FOLDER": os.path.join(folder, "data"), "ROCKET_PORT": str(PORT), "ROCKET_ADDRESS": "127.0.0.1",
        "DOMAIN": VW, "SIGNUPS_ALLOWED": "true", "WEB_VAULT_ENABLED": "false",
        "SSO_ENABLED": "true", "SSO_SAML_ENABLED": "true", "SSO_SAML_IDP_ENTITY_ID": idp_entity,
        "SSO_SAML_IDP_SSO_URL": idp_base + "/sso/redirect", "SSO_SAML_IDP_CERT": crt,
        "SSO_SAML_IDP_SLO_URL": idp_base + "/slo", "SSO_SAML_SP_KEY": sp_key, "SSO_SAML_SP_CERT": sp_crt,
        "SSO_SAML_REQUIRE_ENCRYPTED_ASSERTIONS": "true",
        "SSO_SAML_EMAIL_VERIFIED": "true", "SSO_SIGNUPS_ALLOWED": "true", "SSO_PKCE": "true",
        "LOGIN_RATELIMIT_MAX_BURST": "1000",
    })
    os.makedirs(env["DATA_FOLDER"])
    log = open(os.path.join(folder, "vw.log"), "w")
    vw = subprocess.Popen([base.BIN], env=env, stdout=log, stderr=subprocess.STDOUT)
    try:
        dex.wait_port(PORT); time.sleep(0.4)
        md = ft.http("GET", "/identity/saml/metadata", raw=True, base=VW)
        md = md.decode() if isinstance(md, bytes) else md
        sp_b64 = "".join(open(sp_crt).read().split("-----")[2].split())
        assert 'AuthnRequestsSigned="true"' in md and 'use="encryption"' in md and sp_b64 in md, md
        assert f'Location="{SLO}"' in md, md
        print("  metadata ok: signing/encryption keys + SingleLogoutService")
        md_file = os.path.join(folder, "sp.xml"); open(md_file, "w").write(md)
        idp = samlidp.build_server(idp_base, key, crt, md_file)
        rogue = samlidp.build_server(idp_base, bad_key, bad_crt, md_file)

        def fresh():
            o, _ = base.opener()
            f = base.start_authorize(o)
            req = verify_redirect_sig(f["idp_url"], sp_crt, folder)
            assert f["req_id"] in req
            return o, f

        def resp(server, f, encrypt=True, sign=True):
            r = server.create_authn_response(
                identity={"mail": [base.EMAIL], "displayName": [base.NAME]}, in_response_to=f["req_id"],
                destination=base.ACS, sp_entity_id=base.SP_ENTITY,
                name_id=samlidp.NameID(format=samlidp.NAMEID_FORMAT_EMAILADDRESS, text=base.EMAIL),
                authn={"class_ref": samlidp.PASSWORD, "authn_auth": ""}, sign_assertion=sign, sign_response=False,
                encrypt_assertion=encrypt, encrypt_assertion_self_contained=True,
                encrypt_cert_assertion=sp_b64 if encrypt else None)
            return str(r)

        o, f = fresh()
        print("  signed AuthnRequest ok (RSA-SHA256 over SAMLRequest/RelayState/SigAlg)")
        x = resp(idp, f)
        assert "EncryptedAssertion" in x and base.EMAIL not in x, "assertion should be encrypted"
        login = base.token(base.finish(o, base.post_acs(o, base.b64(x), f["relay"]), f), f["verifier"])
        assert login.get("access_token") and login.get("refresh_token"), login
        print("  encrypted assertion ok: decrypted, signature verified, token issued")

        o, f = fresh()
        base.expect_reject("plaintext assertion when encryption required", base.post_acs(o, base.b64(resp(idp, f, encrypt=False)), f["relay"]))
        o, f = fresh()
        base.expect_reject("encrypted but unsigned", base.post_acs(o, base.b64(resp(idp, f, sign=False)), f["relay"]))
        o, f = fresh()
        base.expect_reject("encrypted, signed by rogue key", base.post_acs(o, base.b64(resp(rogue, f)), f["relay"]))

        # --- IdP-initiated single logout ---
        op, _ = base.opener()
        base.expect_reject("unsigned LogoutRequest", post_slo(op, "SAMLRequest", logout_request(idp_entity, base.EMAIL)))
        base.expect_reject("rogue-signed LogoutRequest", post_slo(op, "SAMLRequest", sign_msg(logout_request(idp_entity, base.EMAIL), bad_key, "LogoutRequest")))
        base.expect_reject("LogoutRequest wrong issuer", post_slo(op, "SAMLRequest", sign_msg(logout_request("https://evil/idp", base.EMAIL), key, "LogoutRequest")))
        refresh(login["refresh_token"])  # still alive after rejected attempts
        lr = sign_msg(logout_request(idp_entity, base.EMAIL), key, "LogoutRequest")
        code, _h, body, nxt = post_slo(op, "SAMLRequest", lr)
        assert code in (302, 303) and nxt.startswith(idp_base + "/slo?"), (code, body[:300], nxt)
        out = verify_redirect_sig(nxt, sp_crt, folder)
        lr_id = re.search(r'\bID="([^"]+)"', lr).group(1)
        assert "LogoutResponse" in out and f'InResponseTo="{lr_id}"' in out and "status:Success" in out, out
        assert_dead(login)
        print("  IdP-initiated SLO ok: signed LogoutResponse, refresh + access tokens revoked")

        # --- SP-initiated single logout ---
        o, f = fresh()
        login = base.token(base.finish(o, base.post_acs(o, base.b64(resp(idp, f)), f["relay"]), f), f["verifier"])
        r = ft.http("POST", "/identity/connect/saml-logout", token=login["access_token"], base=VW)
        out = verify_redirect_sig(r["url"], sp_crt, folder)
        assert r["url"].startswith(idp_base + "/slo?") and "LogoutRequest" in out and base.EMAIL in out, out
        assert_dead(login)
        irt = re.search(r'\bID="([^"]+)"', out).group(1)
        base.expect_reject("unsigned LogoutResponse", post_slo(op, "SAMLResponse", logout_response(idp_entity, irt)))
        code, _h, body, nxt = post_slo(op, "SAMLResponse", sign_msg(logout_response(idp_entity, irt), key, "LogoutResponse"))
        assert code in (302, 303) and nxt == VW + "/#/login", (code, body[:300], nxt)
        print("  SP-initiated SLO ok: signed LogoutRequest, sessions ended, LogoutResponse verified")

        db = sqlite3.connect(os.path.join(env["DATA_FOLDER"], "db.sqlite3"))
        row = db.execute("select password_hash, private_key, akey from users where email=?", (base.EMAIL,)).fetchone()
        assert row and not row[0] and row[1] is None and not row[2], "must stay zero-knowledge"
        db.close()
        blob = b"".join(open(os.path.join(env["DATA_FOLDER"], n), "rb").read() for n in ("db.sqlite3", "db.sqlite3-wal")
                        if os.path.exists(os.path.join(env["DATA_FOLDER"], n)))
        assert open(sp_key, "rb").read().split(b"\n")[1] not in blob
        print("SSO SAML HARDENING PASS")
    finally:
        vw.terminate()
        try: vw.wait(timeout=5)
        except subprocess.TimeoutExpired: vw.kill()
        if os.environ.get("KEEP") != "1":
            shutil.rmtree(folder, ignore_errors=True)
        else:
            print("kept", folder)


if __name__ == "__main__":
    main()
