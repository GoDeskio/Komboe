"""Emergency access that can decrypt only when the grantor already wrapped their user key.

The server stores that ciphertext. It never generates, holds, or recovers a user key.
A grant with no key share stays undecryptable after the wait, including for takeover.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from komboe.platform.crypto import is_sealed
from komboe.platform.server import APIError, now


def _grant(app, grant_id):
    return app.db.one("SELECT * FROM emergency_grants WHERE id = ?", (grant_id,))


def _ready(grant) -> bool:
    if grant["status"] != "initiated" or not grant["initiated_at"]:
        return False
    started = datetime.fromisoformat(grant["initiated_at"].replace("Z", "+00:00"))
    return datetime.now(timezone.utc) >= started + timedelta(seconds=grant["wait_seconds"])


def register(app) -> None:
    @app.route("POST", "/api/emergency")
    def create_grant(app, _m, _q, headers, body):
        grantor = app.user_from_token(headers.get("Authorization"))
        email = str((body or {}).get("granteeEmail") or "").strip().lower()
        access = (body or {}).get("type")
        wait = (body or {}).get("waitSeconds")
        wrapped = (body or {}).get("keyEncrypted")
        if "@" not in email or access not in ("view", "takeover") or not isinstance(wait, int) or wait < 0:
            raise APIError(400, "granteeEmail, type, and waitSeconds are required")
        if wrapped is not None and not is_sealed(wrapped):
            raise APIError(400, "keyEncrypted must be ciphertext produced by the grantor")
        if email == grantor["email"]:
            raise APIError(400, "choose another person")
        gid = str(uuid4())
        app.db.exec(
            """INSERT INTO emergency_grants (id, grantor_id, grantee_email, grantee_id, access_type, status,
               wait_seconds, key_encrypted, initiated_at) VALUES (?, ?, ?, NULL, ?, 'invited', ?, ?, NULL)""",
            (gid, grantor["id"], email, access, wait, wrapped),
        )
        return {"id": gid, "keyShared": wrapped is not None, "object": "emergencyGrant"}

    @app.route("POST", r"/api/emergency/([0-9a-fA-F-]{36})/accept")
    def accept(app, match, _q, headers, _body):
        user = app.user_from_token(headers.get("Authorization"))
        grant = _grant(app, match.group(1))
        if not grant or grant["grantee_email"] != user["email"] or grant["status"] != "invited":
            raise APIError(404, "emergency grant not found")
        app.db.exec("UPDATE emergency_grants SET status = 'accepted', grantee_id = ? WHERE id = ?", (user["id"], grant["id"]))
        return {"status": "accepted", "object": "emergencyGrant"}

    @app.route("POST", r"/api/emergency/([0-9a-fA-F-]{36})/confirm")
    def confirm(app, match, _q, headers, body):
        user = app.user_from_token(headers.get("Authorization"))
        grant = _grant(app, match.group(1))
        if not grant or grant["grantor_id"] != user["id"] or grant["status"] != "accepted":
            raise APIError(404, "emergency grant not found")
        wrapped = (body or {}).get("keyEncrypted", grant["key_encrypted"])
        if wrapped is not None and not is_sealed(wrapped):
            raise APIError(400, "keyEncrypted must be ciphertext")
        app.db.exec("UPDATE emergency_grants SET status = 'confirmed', key_encrypted = ? WHERE id = ?", (wrapped, grant["id"]))
        return {"status": "confirmed", "keyShared": wrapped is not None, "object": "emergencyGrant"}

    @app.route("POST", r"/api/emergency/([0-9a-fA-F-]{36})/initiate")
    def initiate(app, match, _q, headers, _body):
        user = app.user_from_token(headers.get("Authorization"))
        grant = _grant(app, match.group(1))
        if not grant or grant["grantee_id"] != user["id"] or grant["status"] != "confirmed":
            raise APIError(404, "emergency grant not found")
        app.db.exec("UPDATE emergency_grants SET status = 'initiated', initiated_at = ? WHERE id = ?", (now(), grant["id"]))
        return {"status": "initiated", "object": "emergencyGrant"}

    def _open(app, headers, grant_id, expected):
        user = app.user_from_token(headers.get("Authorization"))
        grant = _grant(app, grant_id)
        if not grant or grant["grantee_id"] != user["id"] or grant["access_type"] != expected:
            raise APIError(404, "emergency grant not found")
        if grant["status"] != "initiated" or not _ready(grant):
            raise APIError(403, "the wait period has not elapsed")
        if not grant["key_encrypted"]:
            raise APIError(403, "emergency access cannot decrypt without the grantor's prior key share")
        return grant

    @app.route("POST", r"/api/emergency/([0-9a-fA-F-]{36})/view")
    def view(app, match, _q, headers, _body):
        grant = _open(app, headers, match.group(1), "view")
        ciphers = app.db.all(
            "SELECT id, item_type AS type, name, data FROM ciphers WHERE user_id = ?",
            (grant["grantor_id"],),
        )
        return {"ciphers": ciphers, "keyEncrypted": grant["key_encrypted"], "vaultKeyIncluded": False, "object": "emergencyView"}

    @app.route("POST", r"/api/emergency/([0-9a-fA-F-]{36})/takeover")
    def takeover(app, match, _q, headers, body):
        grant = _open(app, headers, match.group(1), "takeover")
        new_hash = (body or {}).get("newMasterPasswordHash")
        rewrapped = (body or {}).get("wrappedUserKey")
        if not isinstance(new_hash, str) or len(new_hash) < 20 or not is_sealed(rewrapped):
            raise APIError(400, "takeover requires a new password hash and a rewrapped user key")
        app.db.exec(
            "UPDATE users SET password_hash = ?, user_symmetric_key = ? WHERE id = ?",
            (new_hash, rewrapped, grant["grantor_id"]),
        )
        return {"takenOver": True, "vaultKeyIncluded": False, "object": "emergencyTakeover"}
