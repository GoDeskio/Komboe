"""Tags, password-expiry policy, YubiKey unlock material, and PGP login."""
from __future__ import annotations

import hmac
import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from komboe.platform.crypto import is_ciphertext, stretch
from komboe.platform.gpgutil import GpgError, encrypt, public_only, verify
from komboe.platform.server import APIError, now

YUBIKEY_INFO = b"komboe-yubikey-cr-v1"


def yubikey_key(response: bytes) -> bytes:
    material = hashlib.pbkdf2_hmac("sha256", response, YUBIKEY_INFO, 1, 32)
    return stretch(material)


def yubikey_response(secret: bytes, challenge: bytes) -> bytes:
    """Software stand-in for a YubiKey HMAC-SHA1 challenge-response slot."""
    return hmac.new(secret, challenge, hashlib.sha1).digest()


def register(app) -> None:
    @app.route("POST", "/api/tags")
    def create_tag(app, _m, _q, headers, body):
        user = app.user_from_token(headers.get("Authorization"))
        name = body.get("name") if isinstance(body, dict) else None
        if not is_ciphertext(name):
            raise APIError(400, "tag name must be ciphertext")
        tag_id = str(uuid4())
        app.db.exec("INSERT INTO tags (id, user_id, name) VALUES (?, ?, ?)", (tag_id, user["id"], name))
        return {"id": tag_id, "object": "tag"}

    @app.route("POST", "/api/organizations")
    def create_org(app, _m, _q, headers, body):
        user = app.user_from_token(headers.get("Authorization"))
        name = (body or {}).get("name") or ""
        if not isinstance(name, str) or not name.strip():
            raise APIError(400, "name required")
        org_id = str(uuid4())
        app.db.exec(
            "INSERT INTO organizations (id, owner_id, name) VALUES (?, ?, ?)",
            (org_id, user["id"], name.strip()),
        )
        return {"id": org_id, "object": "organization"}

    @app.route("PUT", r"/api/organizations/([0-9a-fA-F-]{36})/policies/password-expiry")
    def put_expiry(app, match, _q, headers, body):
        user = app.user_from_token(headers.get("Authorization"))
        org_id = match.group(1)
        if not app.db.one("SELECT id FROM organizations WHERE id = ? AND owner_id = ?", (org_id, user["id"])):
            raise APIError(404, "organization not found")
        enabled = bool((body or {}).get("enabled"))
        days = (body or {}).get("maxAgeDays")
        if not isinstance(days, int) or days < 1 or days > 3650:
            raise APIError(400, "maxAgeDays must be 1..3650")
        import json
        app.db.exec("DELETE FROM org_policies WHERE org_id = ? AND policy = ?", (org_id, "password-expiry"))
        app.db.exec(
            "INSERT INTO org_policies (org_id, policy, enabled, data) VALUES (?, ?, ?, ?)",
            (org_id, "password-expiry", 1 if enabled else 0, json.dumps({"maxAgeDays": days})),
        )
        return {"enabled": enabled, "maxAgeDays": days, "object": "policy"}

    @app.route("GET", r"/api/organizations/([0-9a-fA-F-]{36})/reports/password-expiry")
    def expiry_report(app, match, _q, headers, _body):
        import json
        user = app.user_from_token(headers.get("Authorization"))
        org_id = match.group(1)
        if not app.db.one("SELECT id FROM organizations WHERE id = ? AND owner_id = ?", (org_id, user["id"])):
            raise APIError(404, "organization not found")
        policy = app.db.one(
            "SELECT enabled, data FROM org_policies WHERE org_id = ? AND policy = ?",
            (org_id, "password-expiry"),
        )
        if not policy or not policy["enabled"]:
            return {"expired": [], "object": "passwordExpiryReport"}
        days = json.loads(policy["data"])["maxAgeDays"]
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        expired = []
        rows = app.db.all(
            """SELECT id, password_changed_at FROM ciphers
               WHERE organization_id = ? AND user_id = ?""",
            (org_id, user["id"]),
        )
        for row in rows:
            if not row["password_changed_at"]:
                expired.append(row["id"])
                continue
            changed = datetime.fromisoformat(row["password_changed_at"].replace("Z", "+00:00"))
            if changed < cutoff:
                expired.append(row["id"])
        return {"expired": expired, "maxAgeDays": days, "object": "passwordExpiryReport"}

    @app.route("PUT", "/api/yubikey/unlock")
    def enroll_yubikey(app, _m, _q, headers, body):
        user = app.user_from_token(headers.get("Authorization"))
        challenge = (body or {}).get("challenge")
        wrapped = (body or {}).get("wrappedUserKey")
        if not isinstance(challenge, str) or len(challenge) < 8:
            raise APIError(400, "challenge required")
        if not is_ciphertext(wrapped):
            raise APIError(400, "wrappedUserKey must be ciphertext")
        for banned in ("secret", "response", "hmac"):
            if banned in (body or {}):
                raise APIError(400, "the server does not accept YubiKey secrets or responses")
        app.db.exec("DELETE FROM yubikey_unlock WHERE user_id = ?", (user["id"],))
        app.db.exec(
            "INSERT INTO yubikey_unlock (user_id, challenge, wrapped_user_key) VALUES (?, ?, ?)",
            (user["id"], challenge, wrapped),
        )
        return {"enrolled": True, "object": "yubikeyUnlock"}

    @app.route("GET", "/api/yubikey/unlock")
    def get_yubikey(app, _m, _q, headers, _body):
        user = app.user_from_token(headers.get("Authorization"))
        row = app.db.one(
            "SELECT challenge, wrapped_user_key FROM yubikey_unlock WHERE user_id = ?",
            (user["id"],),
        )
        if not row:
            raise APIError(404, "YubiKey unlock is not enrolled")
        return {"challenge": row["challenge"], "wrappedUserKey": row["wrapped_user_key"], "object": "yubikeyUnlock"}

    @app.route("PUT", "/api/pgp/identity")
    def put_pgp(app, _m, _q, headers, body):
        user = app.user_from_token(headers.get("Authorization"))
        public = (body or {}).get("publicKey") or ""
        if not public_only(public):
            raise APIError(400, "a public key block is required; private keys are refused")
        app.db.exec("DELETE FROM pgp_identities WHERE user_id = ?", (user["id"],))
        app.db.exec("INSERT INTO pgp_identities (user_id, public_key) VALUES (?, ?)", (user["id"], public))
        return {"registered": True, "object": "pgpIdentity"}

    @app.route("POST", "/api/pgp/challenge")
    def pgp_challenge(app, _m, _q, _headers, body):
        email = str((body or {}).get("email") or "").strip().lower()
        user = app.db.one(
            """SELECT u.id, p.public_key FROM users u JOIN pgp_identities p ON p.user_id = u.id
               WHERE u.email = ?""",
            (email,),
        )
        if not user:
            raise APIError(404, "no PGP identity for that account")
        nonce = os.urandom(32)
        try:
            armored = encrypt(user["public_key"], nonce)
        except GpgError as exc:
            raise APIError(400, f"could not encrypt the challenge: {exc}") from exc
        cid = str(uuid4())
        app.db.exec(
            "INSERT INTO pgp_challenges (id, user_id, nonce, used) VALUES (?, ?, ?, 0)",
            (cid, user["id"], nonce.hex(),),
        )
        return {"id": cid, "encryptedNonce": armored, "object": "pgpChallenge"}

    @app.route("POST", "/api/pgp/verify")
    def pgp_verify(app, _m, _q, _headers, body):
        cid = (body or {}).get("id")
        signature = (body or {}).get("signature") or ""
        row = app.db.one(
            """SELECT c.user_id, c.nonce, c.used, p.public_key FROM pgp_challenges c
               JOIN pgp_identities p ON p.user_id = c.user_id WHERE c.id = ?""",
            (cid,),
        )
        if not row or row["used"]:
            raise APIError(401, "challenge is not valid")
        try:
            verify(row["public_key"], bytes.fromhex(row["nonce"]), signature)
        except (GpgError, ValueError) as exc:
            raise APIError(401, "signature rejected") from exc
        app.db.exec("UPDATE pgp_challenges SET used = 1 WHERE id = ?", (cid,))
        token = secrets.token_urlsafe(32)
        app.db.exec(
            "INSERT INTO sessions (token_hash, user_id, created_at) VALUES (?, ?, ?)",
            (hashlib.sha256(token.encode()).hexdigest(), row["user_id"], now()),
        )
        return {
            "accessToken": token,
            "authMethod": "pgp",
            "vaultKeyIncluded": False,
            "object": "auth",
        }
