"""Minimal real SAML 2.0 IdP for Komboe tests, built on pysaml2 (xmlsec1 signs).

Not shipped. Key/cert are generated per run by the caller (see make_keypair).
SSO endpoint: HTTP-Redirect binding; response: HTTP-POST binding with a signed Assertion.
"""
import os
import secrets
import subprocess
import threading
import urllib.parse
from html import escape
from wsgiref.simple_server import make_server, WSGIRequestHandler

from saml2 import BINDING_HTTP_POST, BINDING_HTTP_REDIRECT
from saml2.config import IdPConfig
from saml2.saml import NAMEID_FORMAT_EMAILADDRESS, NameID
from saml2.server import Server
from saml2.authn_context import AuthnBroker, PASSWORD, authn_context_class_ref


def resign(xml, key, xmlsec1=None):
    """Re-sign the (already templated) Assertion with xmlsec1, for crafting validly signed bad assertions."""
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False) as f:
        f.write(xml)
    out = subprocess.run([xmlsec1 or os.environ.get("XMLSEC1", "/usr/bin/xmlsec1"), "--sign", "--privkey-pem", key,
                          "--id-attr:ID", "urn:oasis:names:tc:SAML:2.0:assertion:Assertion", f.name],
                         check=True, capture_output=True, text=True).stdout
    os.unlink(f.name)
    return out


def make_keypair(folder, name="idp"):
    key, crt = os.path.join(folder, name + ".key"), os.path.join(folder, name + ".crt")
    subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "2",
                    "-subj", f"/CN=komboe-test-{name}", "-keyout", key, "-out", crt],
                   check=True, capture_output=True)
    os.chmod(key, 0o600)
    return key, crt


def build_server(base_url, key, crt, sp_metadata_file):
    cfg = IdPConfig()
    cfg.load({
        "entityid": base_url + "/metadata",
        "service": {"idp": {
            "endpoints": {"single_sign_on_service": [(base_url + "/sso/redirect", BINDING_HTTP_REDIRECT)]},
            "name_id_format": [NAMEID_FORMAT_EMAILADDRESS],
            "sign_response": False,
            "sign_assertion": True,
            "want_authn_requests_signed": False,
        }},
        "key_file": key,
        "cert_file": crt,
        "metadata": {"local": [sp_metadata_file]},
        "xmlsec_binary": os.environ.get("XMLSEC1", "/usr/bin/xmlsec1"),
    })
    return Server(config=cfg)


def signed_response(idp, req_id, destination, sp_entity, email, name, sign=True):
    broker = AuthnBroker()
    broker.add(authn_context_class_ref(PASSWORD), "")
    resp = idp.create_authn_response(
        identity={"mail": [email], "displayName": [name]},
        in_response_to=req_id, destination=destination, sp_entity_id=sp_entity,
        name_id=NameID(format=NAMEID_FORMAT_EMAILADDRESS, text=email),
        authn=broker.get_authn_by_accr(PASSWORD), sign_assertion=sign, sign_response=False,
    )
    return str(resp)


class IdP:
    def __init__(self, port, key, crt, sp_metadata_file, users):
        self.base = f"http://127.0.0.1:{port}"
        self.server = build_server(self.base, key, crt, sp_metadata_file)
        self.users, self.pending, self.port = users, {}, port

    def app(self, environ, start):
        path, method = environ["PATH_INFO"], environ["REQUEST_METHOD"]
        if path == "/sso/redirect" and method == "GET":
            q = urllib.parse.parse_qs(environ.get("QUERY_STRING", ""))
            req = self.server.parse_authn_request(q["SAMLRequest"][0], BINDING_HTTP_REDIRECT)
            k = secrets.token_urlsafe(16)
            self.pending[k] = (req.message, q.get("RelayState", [""])[0])
            body = (f'<html><body><form method="post" action="/login"><input type="hidden" name="key" value="{k}">'
                    '<input name="username"><input name="password" type="password"><button>Sign in</button>'
                    '</form></body></html>')
            start("200 OK", [("Content-Type", "text/html")])
            return [body.encode()]
        if path == "/login" and method == "POST":
            n = int(environ.get("CONTENT_LENGTH") or 0)
            f = {k: v[0] for k, v in urllib.parse.parse_qs(environ["wsgi.input"].read(n).decode()).items()}
            entry = self.pending.pop(f.get("key", ""), None)
            u = self.users.get(f.get("username", ""))
            if not entry or not u or u["password"] != f.get("password"):
                start("403 Forbidden", [("Content-Type", "text/plain")])
                return [b"bad login"]
            req, relay = entry
            dest = req.assertion_consumer_service_url
            xml = signed_response(self.server, req.id, dest, req.issuer.text, f["username"], u["name"])
            import base64
            b64 = base64.b64encode(xml.encode()).decode()
            body = (f'<html><body onload="document.forms[0].submit()"><form method="post" action="{escape(dest)}">'
                    f'<input type="hidden" name="SAMLResponse" value="{b64}">'
                    f'<input type="hidden" name="RelayState" value="{escape(relay)}">'
                    '<noscript><button>Continue</button></noscript></form></body></html>')
            start("200 OK", [("Content-Type", "text/html")])
            return [body.encode()]
        start("404 Not Found", [("Content-Type", "text/plain")])
        return [b"not found"]

    def start(self):
        class Quiet(WSGIRequestHandler):
            def log_message(self, *a): pass
        self.httpd = make_server("127.0.0.1", self.port, self.app, handler_class=Quiet)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        return self

    def stop(self):
        self.httpd.shutdown()
