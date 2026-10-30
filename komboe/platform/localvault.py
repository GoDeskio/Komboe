"""Local-only vault file. No sockets, no server, no account.

The file holds ciphertext. The master password is stretched in-process and
never written. Opening the file without the password does not reveal items.
"""
from __future__ import annotations

import sqlite3
import threading
import uuid
from datetime import datetime, timezone

from komboe.platform.crypto import dec_str, enc_str, master_key, password_hash, stretch


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


class LocalVault:
    def __init__(self, path: str, email: str, password: str, iterations: int = 600_000):
        self.path = path
        self.email = email
        self._key = stretch(master_key(password, email, iterations))
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS meta (email TEXT, kdf_iterations INTEGER, password_hash TEXT)"""
        )
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS items (
                   id TEXT PRIMARY KEY, item_type INTEGER, name TEXT, data TEXT, created_at TEXT)"""
        )
        row = self._conn.execute("SELECT password_hash FROM meta").fetchone()
        digest = password_hash(master_key(password, email, iterations), password)
        if row is None:
            self._conn.execute(
                "INSERT INTO meta (email, kdf_iterations, password_hash) VALUES (?, ?, ?)",
                (email, iterations, digest),
            )
        elif row[0] != digest:
            raise ValueError("wrong master password")
        self._conn.commit()

    def add_item(self, item_type: int, name: str, fields: dict) -> str:
        import json
        item_id = str(uuid.uuid4())
        with self._lock:
            self._conn.execute(
                "INSERT INTO items (id, item_type, name, data, created_at) VALUES (?, ?, ?, ?, ?)",
                (item_id, item_type, enc_str(name, self._key), enc_str(json.dumps(fields), self._key), _now()),
            )
            self._conn.commit()
        return item_id

    def items(self) -> list[dict]:
        import json
        with self._lock:
            rows = list(self._conn.execute("SELECT id, item_type, name, data, created_at FROM items"))
        out = []
        for item_id, item_type, name, data, _created in rows:
            out.append({
                "id": item_id,
                "type": item_type,
                "name": dec_str(name, self._key),
                "fields": json.loads(dec_str(data, self._key)),
            })
        return out

    def close(self) -> None:
        self._key = b"\x00" * 64
        self._conn.close()
