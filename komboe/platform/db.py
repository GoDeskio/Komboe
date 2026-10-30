"""SQLite storage for the Komboe platform. Postgres is selected with a URL."""
from __future__ import annotations

import sqlite3
import threading
from typing import Any


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    name TEXT,
    kdf_iterations INTEGER NOT NULL,
    password_hash TEXT NOT NULL,
    user_symmetric_key TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    public_key TEXT,
    encrypted_private_key TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ciphers (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    organization_id TEXT,
    item_type INTEGER NOT NULL,
    name TEXT NOT NULL,
    data TEXT,
    notes TEXT,
    favorite INTEGER NOT NULL DEFAULT 0,
    password_changed_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tags (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    name TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS cipher_tags (
    cipher_id TEXT NOT NULL,
    tag_id TEXT NOT NULL,
    PRIMARY KEY (cipher_id, tag_id)
);
CREATE TABLE IF NOT EXISTS organizations (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS org_policies (
    org_id TEXT NOT NULL,
    policy TEXT NOT NULL,
    enabled INTEGER NOT NULL,
    data TEXT NOT NULL,
    PRIMARY KEY (org_id, policy)
);
CREATE TABLE IF NOT EXISTS yubikey_unlock (
    user_id TEXT PRIMARY KEY,
    challenge TEXT NOT NULL,
    wrapped_user_key TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pgp_identities (
    user_id TEXT PRIMARY KEY,
    public_key TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pgp_challenges (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    nonce TEXT NOT NULL,
    used INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS sso_configs (
    org_id TEXT PRIMARY KEY,
    protocol TEXT NOT NULL,
    issuer TEXT NOT NULL,
    client_id TEXT NOT NULL,
    client_secret TEXT,
    certificate TEXT
);
CREATE TABLE IF NOT EXISTS scim_tokens (
    org_id TEXT PRIMARY KEY,
    token_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS directory_configs (
    org_id TEXT PRIMARY KEY,
    url TEXT NOT NULL,
    bind_dn TEXT NOT NULL,
    bind_password TEXT NOT NULL,
    base_dn TEXT NOT NULL,
    filter TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS org_members (
    org_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    two_factor INTEGER NOT NULL DEFAULT 0,
    access_all INTEGER NOT NULL DEFAULT 0,
    last_seen TEXT,
    PRIMARY KEY (org_id, user_id)
);
CREATE TABLE IF NOT EXISTS trusted_devices (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    public_key TEXT NOT NULL,
    wrapped_user_key TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS device_nonces (
    device_id TEXT PRIMARY KEY,
    nonce TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS login_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL,
    success INTEGER NOT NULL,
    device TEXT,
    country TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS siem_configs (
    org_id TEXT PRIMARY KEY,
    host TEXT NOT NULL,
    port INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS org_events (
    id TEXT PRIMARY KEY,
    org_id TEXT NOT NULL,
    type TEXT NOT NULL,
    actor TEXT NOT NULL,
    ip TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS idp_users (
    email TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS oidc_codes (
    code TEXT PRIMARY KEY,
    email TEXT NOT NULL,
    client_id TEXT NOT NULL,
    nonce TEXT,
    expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS secret_projects (
    id TEXT PRIMARY KEY,
    org_id TEXT NOT NULL,
    name TEXT NOT NULL,
    wrapped_key TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS secret_values (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    key_name TEXT NOT NULL,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS service_accounts (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    name TEXT NOT NULL,
    public_key TEXT NOT NULL,
    token_hash TEXT NOT NULL,
    wrapped_key TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS emergency_grants (
    id TEXT PRIMARY KEY,
    grantor_id TEXT NOT NULL,
    grantee_email TEXT NOT NULL,
    grantee_id TEXT,
    access_type TEXT NOT NULL,
    status TEXT NOT NULL,
    wait_seconds INTEGER NOT NULL,
    key_encrypted TEXT,
    initiated_at TEXT
);
"""


class Database:
    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()
        self._postgres = path.startswith("postgres://") or path.startswith("postgresql://")
        if self._postgres:
            import psycopg2
            import psycopg2.extras
            self.conn = psycopg2.connect(path)
            self.conn.autocommit = False
            self._factory = psycopg2.extras.RealDictCursor
            schema = SCHEMA.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "BIGSERIAL PRIMARY KEY")
            schema = schema.replace("INSERT OR REPLACE", "INSERT")
            with self._lock:
                cur = self.conn.cursor()
                for statement in schema.split(";"):
                    if statement.strip():
                        cur.execute(statement)
                self.conn.commit()
        else:
            self.conn = sqlite3.connect(path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            self._factory = None
            with self._lock:
                self.conn.executescript(SCHEMA)
                self.conn.commit()

    def _sql(self, sql: str) -> str:
        return sql.replace("?", "%s") if self._postgres else sql

    def exec(self, sql: str, args: tuple = ()) -> None:
        with self._lock:
            cur = self.conn.cursor(cursor_factory=self._factory) if self._postgres else self.conn.cursor()
            cur.execute(self._sql(sql), args)
            self.conn.commit()

    def all(self, sql: str, args: tuple = ()) -> list[dict[str, Any]]:
        with self._lock:
            cur = self.conn.cursor(cursor_factory=self._factory) if self._postgres else self.conn.cursor()
            cur.execute(self._sql(sql), args)
            rows = cur.fetchall()
        return [dict(r) for r in rows]

    def one(self, sql: str, args: tuple = ()) -> dict[str, Any] | None:
        rows = self.all(sql, args)
        return rows[0] if rows else None
