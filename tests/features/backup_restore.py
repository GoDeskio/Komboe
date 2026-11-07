#!/usr/bin/env python3
"""The server CLI can back up and restore its SQLite database."""
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_command_is_documented():
    main = (ROOT / "server/upstream/src/main.rs").read_text()
    db = (ROOT / "server/upstream/src/db/mod.rs").read_text()
    running = (ROOT / "docs/RUNNING.md").read_text()
    deploy = (ROOT / "deploy/coolify/README.md").read_text()
    assert 'command == "backup"' in main
    assert 'command == "restore"' in main
    assert "komboe restore <backup.sqlite3>" in main
    assert "fn backup_sqlite" in db
    assert "fn restore_sqlite" in db
    assert b"SQLite format 3\0".decode() in db or "SQLite format 3" in db
    assert "vaultwarden backup" in running
    assert "vaultwarden restore" in running
    assert "komboe backup" in deploy
    assert "komboe restore" in deploy
    assert "POST /admin/config/backup_db" in deploy


def test_sqlite_roundtrip(tmp_path=None):
    """Same steps the CLI uses: VACUUM INTO, then replace the live file and drop -wal."""
    import tempfile

    base = Path(tmp_path) if tmp_path else Path(tempfile.mkdtemp(prefix="komboe-backup-"))
    live = base / "db.sqlite3"
    backup = base / "db_backup.sqlite3"
    conn = sqlite3.connect(live)
    conn.execute("CREATE TABLE item (name TEXT)")
    conn.execute("INSERT INTO item (name) VALUES ('kept')")
    conn.commit()
    conn.close()

    src = sqlite3.connect(f"file:{live}?mode=ro", uri=True)
    escaped = str(backup).replace("'", "''")
    src.execute(f"VACUUM INTO '{escaped}'")
    src.close()

    conn = sqlite3.connect(live)
    conn.execute("UPDATE item SET name = 'changed'")
    conn.commit()
    conn.close()
    wal = Path(str(live) + "-wal")
    wal.write_bytes(b"old-wal")

    header = backup.read_bytes()[:16]
    assert header == b"SQLite format 3\x00"
    tmp = Path(str(live) + ".restore")
    tmp.write_bytes(backup.read_bytes())
    tmp.replace(live)
    wal.unlink()

    assert not wal.exists()
    conn = sqlite3.connect(f"file:{live}?mode=ro", uri=True)
    assert conn.execute("SELECT name FROM item").fetchone()[0] == "kept"
    conn.close()
    notes = base / "notes.txt"
    notes.write_text("not a database!!")
    assert notes.read_bytes()[:16] != b"SQLite format 3\x00"
    print("BACKUP RESTORE PASS")


if __name__ == "__main__":
    test_command_is_documented()
    test_sqlite_roundtrip()
