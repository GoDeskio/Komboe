"""Komboe platform HTTP server.

Zero-knowledge: account registration accepts a master-password *hash* and an
already-encrypted user key. Item names and payloads must be ciphertext.
The raw master password, user key, and item fields are rejected.
"""
from __future__ import annotations

import hashlib
import json
import mimetypes
import re
import secrets
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from komboe.platform.crypto import is_sealed
from komboe.platform.db import Database

ROOT = Path(__file__).resolve().parents[2]
DASHBOARD = Path(__file__).resolve().parent / "dashboard"
BRAND = {
    "komboe-light-transparent.png": ROOT / "branding/logo/variants/komboe-light-transparent.png",
    "komboe-dark-transparent.png": ROOT / "branding/logo/variants/komboe-dark-transparent.png",
    "favicon-32.png": ROOT / "branding/logo/favicon/favicon-32.png",
    "favicon.ico": ROOT / "branding/logo/favicon/favicon.ico",
}
FONTS = {
    "Sora-Regular.woff2": ROOT / "branding/fonts/sora/Sora-Regular.woff2",
    "Sora-SemiBold.woff2": ROOT / "branding/fonts/sora/Sora-SemiBold.woff2",
    "Sora-Bold.woff2": ROOT / "branding/fonts/sora/Sora-Bold.woff2",
}
SECRET_FIELDS = {
    "masterpassword",
    "master_password",
    "plaintextpassword",
    "userkey",
    "vaultkey",
    "privatekey",
}


class APIError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def reject_secret_fields(value, where="body") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower().replace("-", "") in {s.replace("_", "") for s in SECRET_FIELDS} or key.lower() in SECRET_FIELDS:
                raise APIError(400, f"refusing {key}: this server never accepts vault secrets")
            reject_secret_fields(child, f"{where}.{key}")
    elif isinstance(value, list):
        for i, child in enumerate(value):
            reject_secret_fields(child, f"{where}[{i}]")


def require_ciphertext(value, field: str):
    if value is None:
        return None
    if not is_sealed(value):
        raise APIError(400, f"{field} must be ciphertext")
    if len(value) > 1_000_000:
        raise APIError(400, f"{field} is too large")
    return value


class App:
    def __init__(self, db: Database):
        self.db = db
        self.routes: list[tuple[str, re.Pattern, callable]] = []
        self.login_hooks: list = []

    def route(self, method: str, pattern: str):
        def deco(fn):
            self.routes.append((method, re.compile(pattern), fn))
            return fn
        return deco

    def user_from_token(self, header: str | None):
        if not header or not header.startswith("Bearer "):
            raise APIError(401, "missing token")
        digest = hashlib.sha256(header[7:].encode()).hexdigest()
        row = self.db.one(
            "SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token_hash = ?",
            (digest,),
        )
        if not row:
            raise APIError(401, "invalid token")
        return row

    def dispatch(self, method: str, path: str, query: dict, headers, body: bytes):
        static = static_response(path)
        if static is not None and method == "GET":
            return static
        payload = None
        if body:
            try:
                payload = json.loads(body.decode())
            except json.JSONDecodeError as exc:
                raise APIError(400, "invalid JSON") from exc
            reject_secret_fields(payload)
        for route_method, pattern, fn in self.routes:
            if route_method != method:
                continue
            match = pattern.fullmatch(path)
            if match:
                result = fn(self, match, query, headers, payload)
                if isinstance(result, tuple):
                    return result
                return 200, result, "application/json"
        raise APIError(404, "not found")


def static_response(path: str):
    files = {
        "/": DASHBOARD / "index.html",
        "/app.css": DASHBOARD / "app.css",
        "/app.js": DASHBOARD / "app.js",
        "/crypto.js": DASHBOARD / "crypto.js",
    }
    target = files.get(path)
    if path.startswith("/brand/"):
        target = BRAND.get(path[len("/brand/"):])
    elif path.startswith("/fonts/"):
        target = FONTS.get(path[len("/fonts/"):])
    if target is None or not Path(target).is_file():
        return None
    data = Path(target).read_bytes()
    ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
    if str(target).endswith(".js"):
        ctype = "text/javascript; charset=utf-8"
    elif str(target).endswith(".css"):
        ctype = "text/css; charset=utf-8"
    elif str(target).endswith(".html"):
        ctype = "text/html; charset=utf-8"
    elif str(target).endswith(".woff2"):
        ctype = "font/woff2"
    return 200, data, ctype


def register_routes(app: App) -> None:
    @app.route("POST", "/api/accounts/register")
    def register(app: App, _m, _q, _h, body):
        if not isinstance(body, dict):
            raise APIError(400, "expected object")
        email = str(body.get("email") or "").strip().lower()
        pw_hash = body.get("masterPasswordHash")
        key = body.get("userSymmetricKey")
        iterations = body.get("kdfIterations")
        if not email or "@" not in email:
            raise APIError(400, "email required")
        if not isinstance(pw_hash, str) or len(pw_hash) < 20:
            raise APIError(400, "masterPasswordHash required")
        require_ciphertext(key, "userSymmetricKey")
        if not isinstance(iterations, int) or iterations < 100_000:
            raise APIError(400, "kdfIterations too small")
        encrypted_private = body.get("encryptedPrivateKey")
        if encrypted_private:
            require_ciphertext(encrypted_private, "encryptedPrivateKey")
        if app.db.one("SELECT id FROM users WHERE email = ?", (email,)):
            raise APIError(409, "account already exists")
        user_id = str(uuid4())
        app.db.exec(
            """INSERT INTO users (id, email, name, kdf_iterations, password_hash, user_symmetric_key,
               public_key, encrypted_private_key, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, email, body.get("name") or "", iterations, pw_hash, key,
             body.get("publicKey"), encrypted_private, now()),
        )
        return {"id": user_id, "email": email, "object": "register"}

    @app.route("POST", "/identity/login")
    def login(app: App, _m, _q, _h, body):
        if not isinstance(body, dict):
            raise APIError(400, "expected object")
        email = str(body.get("email") or "").strip().lower()
        pw_hash = body.get("masterPasswordHash") or ""
        user = app.db.one("SELECT * FROM users WHERE email = ?", (email,))
        ok = bool(user and user.get("active", 1) and user.get("user_symmetric_key") and isinstance(pw_hash, str)
                  and secrets.compare_digest(user["password_hash"], pw_hash))
        flags = []
        for hook in getattr(app, "login_hooks", []):
            extra = hook(app, email, _h, ok, user)
            if extra:
                flags.extend(extra)
        if not ok:
            raise APIError(401, "invalid credentials")
        token = secrets.token_urlsafe(32)
        app.db.exec(
            "INSERT INTO sessions (token_hash, user_id, created_at) VALUES (?, ?, ?)",
            (hashlib.sha256(token.encode()).hexdigest(), user["id"], now()),
        )
        return {
            "accessToken": token,
            "kdf": 0,
            "kdfIterations": user["kdf_iterations"],
            "userSymmetricKey": user["user_symmetric_key"],
            "vaultKeyIncluded": False,
            "anomaly": flags,
            "object": "auth",
        }

    @app.route("GET", "/api/sync")
    def sync(app: App, _m, _q, headers, _body):
        user = app.user_from_token(headers.get("Authorization"))
        ciphers = app.db.all(
            """SELECT id, organization_id, item_type, name, data, notes, favorite, password_changed_at, created_at, updated_at
               FROM ciphers WHERE user_id = ? ORDER BY updated_at""",
            (user["id"],),
        )
        links = app.db.all(
            """SELECT ct.cipher_id, ct.tag_id FROM cipher_tags ct
               JOIN tags t ON t.id = ct.tag_id WHERE t.user_id = ?""",
            (user["id"],),
        )
        by_cipher: dict[str, list[str]] = {}
        for link in links:
            by_cipher.setdefault(link["cipher_id"], []).append(link["tag_id"])
        for row in ciphers:
            row["type"] = row.pop("item_type")
            row["favorite"] = bool(row["favorite"])
            row["organizationId"] = row.pop("organization_id")
            row["tagIds"] = by_cipher.get(row["id"], [])
        tags = app.db.all("SELECT id, name FROM tags WHERE user_id = ?", (user["id"],))
        return {
            "profile": {"id": user["id"], "email": user["email"], "name": user["name"]},
            "ciphers": ciphers,
            "tags": tags,
            "object": "sync",
        }

    @app.route("POST", "/api/ciphers")
    def create_cipher(app: App, _m, _q, headers, body):
        user = app.user_from_token(headers.get("Authorization"))
        if not isinstance(body, dict):
            raise APIError(400, "expected object")
        name = require_ciphertext(body.get("name"), "name")
        data = require_ciphertext(body.get("data"), "data") if body.get("data") else None
        notes = require_ciphertext(body.get("notes"), "notes") if body.get("notes") else None
        item_type = body.get("type", 1)
        if not isinstance(item_type, int) or item_type < 1 or item_type > 64:
            raise APIError(400, "invalid type")
        changed = body.get("passwordChangedAt")
        if changed is not None:
            try:
                datetime.fromisoformat(str(changed).replace("Z", "+00:00"))
            except ValueError as exc:
                raise APIError(400, "passwordChangedAt must be a timestamp") from exc
        org_id = body.get("organizationId")
        if org_id is not None:
            org = app.db.one("SELECT id FROM organizations WHERE id = ? AND owner_id = ?", (org_id, user["id"]))
            if not org:
                raise APIError(404, "organization not found")
        tag_ids = body.get("tagIds") or []
        if not isinstance(tag_ids, list):
            raise APIError(400, "tagIds must be a list")
        for tag_id in tag_ids:
            if not app.db.one("SELECT id FROM tags WHERE id = ? AND user_id = ?", (tag_id, user["id"])):
                raise APIError(404, "tag not found")
        cid = str(uuid4())
        stamp = now()
        app.db.exec(
            """INSERT INTO ciphers (id, user_id, organization_id, item_type, name, data, notes, favorite,
               password_changed_at, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (cid, user["id"], org_id, item_type, name, data, notes, 1 if body.get("favorite") else 0,
             changed, stamp, stamp),
        )
        for tag_id in tag_ids:
            app.db.exec("INSERT INTO cipher_tags (cipher_id, tag_id) VALUES (?, ?)", (cid, tag_id))
        return 200, {"id": cid, "object": "cipher"}, "application/json"

    @app.route("DELETE", r"/api/ciphers/([0-9a-fA-F-]{36})")
    def delete_cipher(app: App, match, _q, headers, _body):
        user = app.user_from_token(headers.get("Authorization"))
        app.db.exec("DELETE FROM ciphers WHERE id = ? AND user_id = ?", (match.group(1), user["id"]))
        return {"ok": True}

    @app.route("GET", "/api/health")
    def health(_app, _m, _q, _h, _b):
        return {"ok": True, "service": "komboe-platform"}


def build_app(db: Database) -> App:
    app = App(db)
    register_routes(app)
    routes_pkg = Path(__file__).resolve().parent / "routes"
    if routes_pkg.is_dir():
        import importlib
        import pkgutil
        import komboe.platform.routes as routes
        for mod in pkgutil.iter_modules(routes.__path__):
            module = importlib.import_module(f"komboe.platform.routes.{mod.name}")
            if hasattr(module, "register"):
                module.register(app)
    return app


def make_handler(app: App):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_GET(self): self._go()
        def do_POST(self): self._go()
        def do_PUT(self): self._go()
        def do_PATCH(self): self._go()
        def do_DELETE(self): self._go()

        def _go(self):
            parsed = urlparse(self.path)
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b""
            query = {k: v[0] for k, v in parse_qs(parsed.query).items()}
            try:
                status, payload, ctype = app.dispatch(self.command, parsed.path, query, self.headers, raw)
            except APIError as exc:
                status, payload, ctype = exc.status, {"message": exc.message}, "application/json"
            except Exception as exc:  # noqa: BLE001 — surface as 500 without a traceback to the client
                status, payload, ctype = 500, {"message": str(exc)}, "application/json"
            body = payload if isinstance(payload, (bytes, bytearray)) else json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            return

    return Handler


def serve_in_thread(db_path: str, host: str = "127.0.0.1", port: int = 0):
    db = Database(db_path)
    app = build_app(db)
    httpd = ThreadingHTTPServer((host, port), make_handler(app))
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd, db


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Komboe platform server")
    parser.add_argument("--db", default="komboe-platform.sqlite3")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    db = Database(args.db)
    app = build_app(db)
    httpd = ThreadingHTTPServer((args.host, args.port), make_handler(app))
    print(f"Komboe platform http://{args.host}:{args.port}/", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
