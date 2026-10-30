"""Clean-room org features: SSO (identity only), SCIM, LDAP sync, trusted devices,
syslog export, anomaly flags, risk insights, and a machine secrets manager.

No vault key is released to an IdP, an admin, or a service account in the clear.
"""
from __future__ import annotations

import base64
import hashlib
import json
import secrets
import socket
import zlib
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from xml.sax.saxutils import escape

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from komboe.platform.crypto import is_ciphertext
from komboe.platform.server import APIError, now

def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

def _idp_key(app):
    if not hasattr(app, "idp_key"):
        app.idp_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return app.idp_key

def _sign_jwt(key, payload: dict) -> str:
    header = _b64url(json.dumps({"alg": "RS256", "typ": "JWT"}, separators=(",", ":")).encode())
    body = _b64url(json.dumps(payload, separators=(",", ":")).encode())
    signing = f"{header}.{body}".encode()
    sig = key.sign(signing, padding.PKCS1v15(), hashes.SHA256())
    return f"{header}.{body}.{_b64url(sig)}"

def _verify_jwt(key, token: str) -> dict:
    try:
        header, body, sig = token.split(".")
        pad = "=" * (-len(sig) % 4)
        key.public_key().verify(base64.urlsafe_b64decode(sig + pad), f"{header}.{body}".encode(), padding.PKCS1v15(), hashes.SHA256())
        payload = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    except Exception as exc:
        raise APIError(401, "identity token rejected") from exc
    if any(k.lower() in {"vaultkey", "userkey", "masterpassword", "keyencrypted"} for k in payload):
        raise APIError(400, "SSO identity tokens must not carry vault keys")
    return payload

def _pem_public(key) -> str:
    return key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()

def _identity_session(app, email: str) -> dict:
    user = app.db.one("SELECT * FROM users WHERE email = ?", (email,))
    if not user:
        user_id = str(uuid4())
        app.db.exec(
            """INSERT INTO users (id, email, name, kdf_iterations, password_hash, user_symmetric_key, public_key,
               encrypted_private_key, created_at, active) VALUES (?, ?, ?, 600000, ?, NULL, NULL, NULL, ?, 1)""",
            (user_id, email, email.split("@")[0], secrets.token_hex(16), now()),
        )
        user = app.db.one("SELECT * FROM users WHERE id = ?", (user_id,))
    token = secrets.token_urlsafe(32)
    app.db.exec("INSERT INTO sessions (token_hash, user_id, created_at) VALUES (?, ?, ?)",
                (hashlib.sha256(token.encode()).hexdigest(), user["id"], now()))
    return {"accessToken": token, "authMethod": "sso", "vaultKeyIncluded": False, "userSymmetricKey": None, "object": "auth"}

def _require_org_owner(app, headers, org_id):
    user = app.user_from_token(headers.get("Authorization"))
    if not app.db.one("SELECT id FROM organizations WHERE id = ? AND owner_id = ?", (org_id, user["id"])):
        raise APIError(404, "organization not found")
    return user

def note_login(app, email, headers, ok, user):
    device = headers.get("X-Komboe-Device") or ""
    country = headers.get("X-Komboe-Country") or ""
    stamp = now()
    window = (datetime.now(timezone.utc) - timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    def failures():
        row = app.db.one(
            "SELECT COUNT(*) AS n FROM login_events WHERE email = ? AND success = 0 AND created_at > ?",
            (email, window),
        )
        return row["n"] if row else 0
    if failures() >= 5:
        raise APIError(429, "account locked by anomaly detection")
    if not ok:
        app.db.exec(
            "INSERT INTO login_events (email, success, device, country, created_at) VALUES (?, 0, ?, ?, ?)",
            (email, device, country, stamp),
        )
        if failures() >= 5:
            raise APIError(429, "account locked by anomaly detection")
        return []
    flags = []
    if device:
        seen = app.db.one(
            "SELECT id FROM login_events WHERE email = ? AND success = 1 AND device = ?",
            (email, device),
        )
        if not seen:
            flags.append("new_device")
    if country:
        last = app.db.one(
            "SELECT country, created_at FROM login_events WHERE email = ? AND success = 1 AND country != '' ORDER BY id DESC",
            (email,),
        )
        if last and last["country"] and last["country"] != country:
            previous = datetime.fromisoformat(last["created_at"].replace("Z", "+00:00"))
            if datetime.now(timezone.utc) - previous < timedelta(minutes=10):
                flags.append("impossible_travel")
    app.db.exec(
        "INSERT INTO login_events (email, success, device, country, created_at) VALUES (?, 1, ?, ?, ?)",
        (email, device, country, stamp),
    )
    return flags

def _syslog(host: str, port: int, text: str) -> None:
    msg = f"<134>1 {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')} komboe komboe - - - {text}"
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.sendto(msg.encode(), (host, port))
    finally:
        sock.close()

def register(app) -> None:
    app.login_hooks.append(note_login)

    @app.route("POST", "/idp/users")
    def idp_user(app, _m, _q, _h, body):
        email = str((body or {}).get("email") or "").strip().lower()
        password = (body or {}).get("password") or ""
        if "@" not in email or len(password) < 8:
            raise APIError(400, "email and password required")
        digest = hashlib.sha256(password.encode()).hexdigest()
        app.db.exec("DELETE FROM idp_users WHERE email = ?", (email,))
        app.db.exec("INSERT INTO idp_users (email, password_hash) VALUES (?, ?)", (email, digest))
        return {"email": email, "object": "idpUser"}

    @app.route("GET", "/idp/oidc/jwks")
    def jwks(app, _m, _q, _h, _b):
        pub = _idp_key(app).public_key().public_numbers()
        def enc_int(n):
            raw = n.to_bytes((n.bit_length() + 7) // 8, "big")
            return _b64url(raw)
        return {"keys": [{"kty": "RSA", "use": "sig", "alg": "RS256", "kid": "komboe-idp", "n": enc_int(pub.n), "e": enc_int(pub.e)}]}

    @app.route("POST", "/idp/oidc/authorize")
    def oidc_authorize(app, _m, _q, _h, body):
        email = str((body or {}).get("email") or "").strip().lower()
        password = (body or {}).get("password") or ""
        row = app.db.one("SELECT password_hash FROM idp_users WHERE email = ?", (email,))
        if not row or not secrets.compare_digest(row["password_hash"], hashlib.sha256(password.encode()).hexdigest()):
            raise APIError(401, "identity provider rejected the login")
        code = secrets.token_urlsafe(24)
        app.db.exec(
            "INSERT INTO oidc_codes (code, email, client_id, nonce, expires_at) VALUES (?, ?, ?, ?, ?)",
            (code, email, body.get("clientId"), body.get("nonce") or "", (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()),
        )
        return {"code": code, "state": body.get("state"), "object": "oidcCode"}

    @app.route("POST", "/idp/oidc/token")
    def oidc_token(app, _m, _q, _h, body):
        cfg = app.db.one("SELECT client_secret FROM sso_configs WHERE client_id = ?", ((body or {}).get("clientId"),))
        if not cfg or not secrets.compare_digest(cfg["client_secret"], (body or {}).get("clientSecret") or ""):
            raise APIError(401, "client authentication failed")
        code = app.db.one("SELECT * FROM oidc_codes WHERE code = ?", ((body or {}).get("code"),))
        if not code or code["client_id"] != body.get("clientId"):
            raise APIError(400, "code rejected")
        app.db.exec("DELETE FROM oidc_codes WHERE code = ?", (code["code"],))
        payload = {"iss": "komboe-idp", "aud": code["client_id"], "sub": code["email"], "email": code["email"], "nonce": code["nonce"], "exp": int(datetime.now(timezone.utc).timestamp()) + 300}
        return {"id_token": _sign_jwt(_idp_key(app), payload), "token_type": "Bearer", "object": "oidcToken"}

    @app.route("PUT", r"/api/organizations/([0-9a-fA-F-]{36})/sso")
    def put_sso(app, match, _q, headers, body):
        _require_org_owner(app, headers, match.group(1))
        protocol = (body or {}).get("protocol")
        if protocol not in ("oidc", "saml"):
            raise APIError(400, "protocol must be oidc or saml")
        app.db.exec("DELETE FROM sso_configs WHERE org_id = ?", (match.group(1),))
        app.db.exec(
            """INSERT INTO sso_configs (org_id, protocol, issuer, client_id, client_secret, certificate)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (match.group(1), protocol, body.get("issuer") or "", body.get("clientId") or match.group(1),
             body.get("clientSecret"), body.get("certificate")),
        )
        return {"protocol": protocol, "vaultKeyIncluded": False, "object": "ssoConfig"}

    @app.route("POST", "/api/sso/oidc/callback")
    def oidc_callback(app, _m, _q, _h, body):
        org_id = (body or {}).get("organizationId")
        cfg = app.db.one("SELECT * FROM sso_configs WHERE org_id = ? AND protocol = 'oidc'", (org_id,))
        if not cfg:
            raise APIError(404, "SSO is not configured")
        if body.get("idToken"):
            payload = _verify_jwt(_idp_key(app), body["idToken"])
        else:
            exchanged = oidc_token(app, None, {}, {}, {"clientId": cfg["client_id"], "clientSecret": cfg["client_secret"], "code": body.get("code")})
            payload = _verify_jwt(_idp_key(app), exchanged["id_token"])
        if payload.get("aud") != cfg["client_id"]:
            raise APIError(401, "audience mismatch")
        session = _identity_session(app, payload["email"])
        session["protocol"] = "oidc"
        return session

    @app.route("GET", "/idp/saml/certificate")
    def saml_cert(app, _m, _q, _h, _b):
        return {"certificate": _pem_public(_idp_key(app)), "object": "samlCertificate"}

    @app.route("POST", "/idp/saml/sso")
    def saml_sso(app, _m, _q, _h, body):
        raw = base64.b64decode((body or {}).get("SAMLRequest") or "")
        request = zlib.decompress(raw, -15).decode()
        if "<AuthnRequest" not in request:
            raise APIError(400, "AuthnRequest required")
        email = str(body.get("email") or "").strip().lower()
        password = body.get("password") or ""
        row = app.db.one("SELECT password_hash FROM idp_users WHERE email = ?", (email,))
        if not row or not secrets.compare_digest(row["password_hash"], hashlib.sha256(password.encode()).hexdigest()):
            raise APIError(401, "identity provider rejected the login")
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        later = (datetime.now(timezone.utc) + timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
        assertion = (
            f'<Assertion ID="_a{uuid4().hex}" IssueInstant="{stamp}"><Issuer>komboe-idp</Issuer>'
            f"<Subject><NameID>{escape(email)}</NameID></Subject>"
            f'<Conditions NotOnOrAfter="{later}"><AudienceRestriction><Audience>{escape(body.get("audience") or "")}</Audience></AudienceRestriction></Conditions>'
            f"</Assertion>"
        )
        sig = base64.b64encode(_idp_key(app).sign(assertion.encode(), padding.PKCS1v15(), hashes.SHA256())).decode()
        response = f'<Response IssueInstant="{stamp}">{assertion}<Signature>{sig}</Signature></Response>'
        return {"SAMLResponse": base64.b64encode(response.encode()).decode(), "object": "samlResponse"}

    @app.route("POST", "/api/sso/saml/acs")
    def saml_acs(app, _m, _q, _h, body):
        org_id = (body or {}).get("organizationId")
        cfg = app.db.one("SELECT * FROM sso_configs WHERE org_id = ? AND protocol = 'saml'", (org_id,))
        if not cfg or not cfg["certificate"]:
            raise APIError(404, "SAML is not configured")
        try:
            response = base64.b64decode(body.get("SAMLResponse") or "").decode()
            assertion = response.split("<Signature>")[0].split("<Response")[1]
            assertion = assertion[assertion.index("<Assertion"):assertion.index("</Assertion>") + len("</Assertion>")]
            sig = base64.b64decode(response.split("<Signature>")[1].split("</Signature>")[0])
            pub = serialization.load_pem_public_key(cfg["certificate"].encode())
            pub.verify(sig, assertion.encode(), padding.PKCS1v15(), hashes.SHA256())
        except Exception as exc:
            raise APIError(401, "SAML signature rejected") from exc
        if "VaultKey" in response or "userSymmetricKey" in response:
            raise APIError(400, "SAML assertions must not carry vault keys")
        if f"<Audience>{org_id}</Audience>" not in response:
            raise APIError(401, "audience mismatch")
        email = response.split("<NameID>")[1].split("</NameID>")[0]
        session = _identity_session(app, email)
        session["protocol"] = "saml"
        return session

    @app.route("POST", r"/api/organizations/([0-9a-fA-F-]{36})/scim-token")
    def scim_token(app, match, _q, headers, _body):
        _require_org_owner(app, headers, match.group(1))
        token = "scim_" + secrets.token_urlsafe(24)
        app.db.exec("DELETE FROM scim_tokens WHERE org_id = ?", (match.group(1),))
        app.db.exec("INSERT INTO scim_tokens (org_id, token_hash) VALUES (?, ?)",
                    (match.group(1), hashlib.sha256(token.encode()).hexdigest()))
        return {"token": token, "object": "scimToken"}

    def scim_org(app, headers):
        header = headers.get("Authorization") or ""
        if not header.startswith("Bearer scim_"):
            raise APIError(401, "SCIM token required")
        digest = hashlib.sha256(header[7:].encode()).hexdigest()
        row = app.db.one("SELECT org_id FROM scim_tokens WHERE token_hash = ?", (digest,))
        if not row:
            raise APIError(401, "SCIM token required")
        return row["org_id"]

    def scim_user(row):
        return {"schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"], "id": row["id"], "userName": row["email"],
                "active": bool(row["active"]), "emails": [{"value": row["email"], "primary": True}], "meta": {"resourceType": "User"}}

    @app.route("POST", "/scim/v2/Users")
    def scim_create(app, _m, _q, headers, body):
        org_id = scim_org(app, headers)
        email = str((body or {}).get("userName") or "").strip().lower()
        if "@" not in email:
            raise APIError(400, "userName required")
        if any(k.lower() in {"password", "vaultkey", "userkey"} for k in (body or {})):
            raise APIError(400, "SCIM provisioning does not accept passwords or vault keys")
        user_id = str(uuid4())
        app.db.exec(
            """INSERT INTO users (id, email, name, kdf_iterations, password_hash, user_symmetric_key, public_key,
               encrypted_private_key, created_at, active) VALUES (?, ?, ?, 600000, ?, NULL, NULL, NULL, ?, ?)""",
            (user_id, email, email.split("@")[0], secrets.token_hex(16), now(), 1 if body.get("active", True) else 0),
        )
        app.db.exec("INSERT OR REPLACE INTO org_members (org_id, user_id, two_factor, access_all, last_seen) VALUES (?, ?, 0, 0, ?)",
                    (org_id, user_id, now()))
        return scim_user(app.db.one("SELECT * FROM users WHERE id = ?", (user_id,)))

    @app.route("GET", "/scim/v2/Users")
    def scim_list(app, _m, _q, headers, _b):
        org_id = scim_org(app, headers)
        rows = app.db.all(
            """SELECT u.* FROM users u JOIN org_members m ON m.user_id = u.id WHERE m.org_id = ?""",
            (org_id,),
        )
        return {"Resources": [scim_user(r) for r in rows], "totalResults": len(rows), "schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"]}

    @app.route("PATCH", r"/scim/v2/Users/([0-9a-fA-F-]{36})")
    def scim_patch(app, match, _q, headers, body):
        org_id = scim_org(app, headers)
        if not app.db.one("SELECT user_id FROM org_members WHERE org_id = ? AND user_id = ?", (org_id, match.group(1))):
            raise APIError(404, "user not found")
        active = True
        for op in (body or {}).get("Operations") or []:
            if op.get("path") == "active":
                active = bool(op.get("value"))
        app.db.exec("UPDATE users SET active = ? WHERE id = ?", (1 if active else 0, match.group(1)))
        return scim_user(app.db.one("SELECT * FROM users WHERE id = ?", (match.group(1),)))

    @app.route("DELETE", r"/scim/v2/Users/([0-9a-fA-F-]{36})")
    def scim_delete(app, match, _q, headers, _b):
        org_id = scim_org(app, headers)
        app.db.exec("DELETE FROM org_members WHERE org_id = ? AND user_id = ?", (org_id, match.group(1)))
        app.db.exec("UPDATE users SET active = 0 WHERE id = ?", (match.group(1),))
        return 204, b"", "application/json"

    @app.route("PUT", r"/api/organizations/([0-9a-fA-F-]{36})/directory")
    def put_directory(app, match, _q, headers, body):
        _require_org_owner(app, headers, match.group(1))
        app.db.exec("DELETE FROM directory_configs WHERE org_id = ?", (match.group(1),))
        app.db.exec(
            """INSERT INTO directory_configs (org_id, url, bind_dn, bind_password, base_dn, filter)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (match.group(1), body["url"], body["bindDn"], body["bindPassword"], body["baseDn"], body.get("filter") or "(objectClass=inetOrgPerson)"),
        )
        return {"configured": True, "object": "directory"}

    @app.route("POST", r"/api/organizations/([0-9a-fA-F-]{36})/directory/sync")
    def directory_sync(app, match, _q, headers, _body):
        _require_org_owner(app, headers, match.group(1))
        cfg = app.db.one("SELECT * FROM directory_configs WHERE org_id = ?", (match.group(1),))
        if not cfg:
            raise APIError(404, "directory is not configured")
        import ldap
        conn = ldap.initialize(cfg["url"])
        conn.simple_bind_s(cfg["bind_dn"], cfg["bind_password"])
        found = conn.search_s(cfg["base_dn"], ldap.SCOPE_SUBTREE, cfg["filter"], ["mail"])
        imported = []
        for _dn, attrs in found:
            mail = attrs.get("mail", [b""])[0].decode()
            if "@" not in mail:
                continue
            existing = app.db.one("SELECT id FROM users WHERE email = ?", (mail,))
            if existing:
                user_id = existing["id"]
            else:
                user_id = str(uuid4())
                app.db.exec(
                    """INSERT INTO users (id, email, name, kdf_iterations, password_hash, user_symmetric_key, public_key,
                       encrypted_private_key, created_at, active) VALUES (?, ?, ?, 600000, ?, NULL, NULL, NULL, ?, 1)""",
                    (user_id, mail, mail.split("@")[0], secrets.token_hex(16), now()),
                )
            app.db.exec("INSERT OR REPLACE INTO org_members (org_id, user_id, two_factor, access_all, last_seen) VALUES (?, ?, 0, 0, ?)",
                        (match.group(1), user_id, now()))
            imported.append(mail)
        conn.unbind_s()
        return {"imported": imported, "vaultKeyIncluded": False, "object": "directorySync"}

    @app.route("PUT", "/api/devices/trust")
    def trust_device(app, _m, _q, headers, body):
        user = app.user_from_token(headers.get("Authorization"))
        wrapped = (body or {}).get("wrappedUserKey")
        public = (body or {}).get("publicKey")
        if not is_ciphertext(wrapped) and not (isinstance(wrapped, str) and wrapped.startswith("4.")):
            raise APIError(400, "wrappedUserKey must be ciphertext")
        if not isinstance(public, str) or len(public) < 32:
            raise APIError(400, "device public key required")
        device_id = str(uuid4())
        app.db.exec(
            "INSERT INTO trusted_devices (id, user_id, public_key, wrapped_user_key) VALUES (?, ?, ?, ?)",
            (device_id, user["id"], public, wrapped),
        )
        return {"deviceId": device_id, "object": "trustedDevice"}

    @app.route("POST", "/api/devices/unlock")
    def device_unlock(app, _m, _q, headers, body):
        user = app.user_from_token(headers.get("Authorization"))
        device = app.db.one("SELECT * FROM trusted_devices WHERE id = ? AND user_id = ?", ((body or {}).get("deviceId"), user["id"]))
        if not device:
            raise APIError(404, "trusted device not found")
        try:
            pub = serialization.load_der_public_key(base64.b64decode(device["public_key"]))
            nonce = base64.b64decode((body or {}).get("nonce") or "")
            sig = base64.b64decode((body or {}).get("signature") or "")
            pub.verify(sig, nonce, padding.PKCS1v15(), hashes.SHA256())
        except Exception as exc:
            raise APIError(401, "device signature rejected") from exc
        if (body or {}).get("nonce") != headers.get("X-Komboe-Nonce"):
            raise APIError(401, "nonce mismatch")
        return {"wrappedUserKey": device["wrapped_user_key"], "vaultKeyIncluded": False, "object": "trustedDeviceUnlock"}

    @app.route("PUT", r"/api/organizations/([0-9a-fA-F-]{36})/siem")
    def put_siem(app, match, _q, headers, body):
        _require_org_owner(app, headers, match.group(1))
        host, port = body.get("host"), body.get("port")
        if host not in ("127.0.0.1", "localhost") or not isinstance(port, int):
            raise APIError(400, "SIEM export is limited to a local collector")
        app.db.exec("DELETE FROM siem_configs WHERE org_id = ?", (match.group(1),))
        app.db.exec("INSERT INTO siem_configs (org_id, host, port) VALUES (?, ?, ?)", (match.group(1), host, port))
        return {"host": host, "port": port, "object": "siem"}

    @app.route("POST", r"/api/organizations/([0-9a-fA-F-]{36})/events")
    def post_event(app, match, _q, headers, body):
        user = _require_org_owner(app, headers, match.group(1))
        kind = str((body or {}).get("type") or "")
        if not kind.replace(".", "").replace("_", "").isalnum() or len(kind) > 64:
            raise APIError(400, "event type must be a short label")
        ip = headers.get("X-Real-IP") or "127.0.0.1"
        app.db.exec(
            "INSERT INTO org_events (id, org_id, type, actor, ip, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (str(uuid4()), match.group(1), kind, user["id"], ip, now()),
        )
        cfg = app.db.one("SELECT host, port FROM siem_configs WHERE org_id = ?", (match.group(1),))
        if cfg:
            _syslog(cfg["host"], cfg["port"], f"org={match.group(1)} type={kind} actor={user['id']} ip={ip}")
        return {"logged": True, "object": "event"}

    @app.route("POST", r"/api/organizations/([0-9a-fA-F-]{36})/members")
    def add_member_meta(app, match, _q, headers, body):
        _require_org_owner(app, headers, match.group(1))
        email = str((body or {}).get("email") or "").strip().lower()
        existing = app.db.one("SELECT id FROM users WHERE email = ?", (email,))
        if existing:
            user_id = existing["id"]
        else:
            user_id = str(uuid4())
            app.db.exec(
                """INSERT INTO users (id, email, name, kdf_iterations, password_hash, user_symmetric_key, public_key,
                   encrypted_private_key, created_at, active) VALUES (?, ?, ?, 600000, ?, NULL, NULL, NULL, ?, 1)""",
                (user_id, email, email.split("@")[0], secrets.token_hex(16), now()),
            )
        app.db.exec(
            "INSERT OR REPLACE INTO org_members (org_id, user_id, two_factor, access_all, last_seen) VALUES (?, ?, ?, ?, ?)",
            (match.group(1), user_id, 1 if body.get("twoFactor") else 0, 1 if body.get("accessAll") else 0, body.get("lastSeen") or now()),
        )
        return {"userId": user_id, "object": "member"}

    @app.route("GET", r"/api/organizations/([0-9a-fA-F-]{36})/risk")
    def risk(app, match, _q, headers, _b):
        _require_org_owner(app, headers, match.group(1))
        members = app.db.all(
            """SELECT u.email, m.two_factor, m.access_all, m.last_seen FROM org_members m
               JOIN users u ON u.id = m.user_id WHERE m.org_id = ?""",
            (match.group(1),),
        )
        cutoff = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
        without = [m["email"] for m in members if not m["two_factor"]]
        stale = [m["email"] for m in members if (m["last_seen"] or "") < cutoff]
        everyone = sum(1 for m in members if m["access_all"])
        return {
            "membersWithout2fa": without, "staleMembers": stale, "collectionsSharedWithEveryone": everyone,
            "memberCount": len(members), "vaultReadable": False, "object": "riskInsights",
        }

    @app.route("POST", r"/api/organizations/([0-9a-fA-F-]{36})/secrets/projects")
    def create_project(app, match, _q, headers, body):
        _require_org_owner(app, headers, match.group(1))
        name, wrapped = body.get("name"), body.get("wrappedProjectKey")
        if not is_ciphertext(name) or not (is_ciphertext(wrapped) or str(wrapped).startswith("4.")):
            raise APIError(400, "project name and key must be ciphertext")
        pid = str(uuid4())
        app.db.exec("INSERT INTO secret_projects (id, org_id, name, wrapped_key) VALUES (?, ?, ?, ?)",
                    (pid, match.group(1), name, wrapped))
        return {"id": pid, "object": "secretProject"}

    @app.route("POST", r"/api/secrets/projects/([0-9a-fA-F-]{36})/secrets")
    def create_secret(app, match, _q, headers, body):
        user = app.user_from_token(headers.get("Authorization"))
        project = app.db.one(
            """SELECT p.* FROM secret_projects p JOIN organizations o ON o.id = p.org_id
               WHERE p.id = ? AND o.owner_id = ?""",
            (match.group(1), user["id"]),
        )
        if not project:
            raise APIError(404, "project not found")
        key_name, value = body.get("key"), body.get("value")
        if not is_ciphertext(key_name) or not is_ciphertext(value):
            raise APIError(400, "secret key and value must be ciphertext")
        sid = str(uuid4())
        app.db.exec("INSERT INTO secret_values (id, project_id, key_name, value) VALUES (?, ?, ?, ?)",
                    (sid, project["id"], key_name, value))
        return {"id": sid, "object": "secret"}

    @app.route("POST", r"/api/secrets/projects/([0-9a-fA-F-]{36})/service-accounts")
    def create_sa(app, match, _q, headers, body):
        user = app.user_from_token(headers.get("Authorization"))
        project = app.db.one(
            """SELECT p.* FROM secret_projects p JOIN organizations o ON o.id = p.org_id
               WHERE p.id = ? AND o.owner_id = ?""",
            (match.group(1), user["id"]),
        )
        if not project:
            raise APIError(404, "project not found")
        wrapped = body.get("wrappedProjectKey")
        if not (is_ciphertext(wrapped) or str(wrapped).startswith("4.")):
            raise APIError(400, "wrappedProjectKey must be ciphertext")
        token = "sa_" + secrets.token_urlsafe(24)
        sid = str(uuid4())
        app.db.exec(
            """INSERT INTO service_accounts (id, project_id, name, public_key, token_hash, wrapped_key)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (sid, project["id"], body.get("name") or "machine", body.get("publicKey") or "", hashlib.sha256(token.encode()).hexdigest(), wrapped),
        )
        return {"id": sid, "accessToken": token, "object": "serviceAccount"}

    @app.route("GET", "/api/secrets/machine/secrets")
    def machine_secrets(app, _m, _q, headers, _b):
        header = headers.get("Authorization") or ""
        if not header.startswith("Bearer sa_"):
            raise APIError(401, "service account token required")
        digest = hashlib.sha256(header[7:].encode()).hexdigest()
        account = app.db.one("SELECT * FROM service_accounts WHERE token_hash = ?", (digest,))
        if not account:
            raise APIError(401, "service account token required")
        secrets_rows = app.db.all("SELECT id, key_name, value FROM secret_values WHERE project_id = ?", (account["project_id"],))
        return {"wrappedProjectKey": account["wrapped_key"], "secrets": secrets_rows, "vaultKeyIncluded": False, "object": "machineSecrets"}
