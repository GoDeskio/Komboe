#!/usr/bin/env python3
"""Boot a throwaway server so diesel applies the new migrations, then boot again on that file."""
import os
import shutil
import sqlite3
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BIN = Path(os.environ.get("KOMBOE_BIN", ROOT / "server/upstream/target/debug/vaultwarden"))
PORT = "18082"
NEED = (
    "komboe_login_names",
    "komboe_email_login_policy",
    "komboe_email_login_trust",
    "komboe_email_login_codes",
    "__diesel_schema_migrations",
)


def wait_alive(proc, log):
    for _ in range(80):
        if proc.poll() is not None:
            raise SystemExit(log.read_text(encoding="utf-8", errors="replace")[-2000:])
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/alive", timeout=1).read()
            return
        except Exception:
            time.sleep(0.25)
    raise SystemExit("server did not stay up\n" + log.read_text(encoding="utf-8", errors="replace")[-2000:])


def tables(db):
    con = sqlite3.connect(db)
    names = {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    versions = [row[0] for row in con.execute("SELECT version FROM __diesel_schema_migrations ORDER BY version")]
    con.close()
    return names, versions


def boot(data, log_path):
    env = os.environ.copy()
    env.update({
        "DATA_FOLDER": str(data),
        "ROCKET_ADDRESS": "127.0.0.1",
        "ROCKET_PORT": PORT,
        "DOMAIN": f"http://127.0.0.1:{PORT}",
        "SIGNUPS_ALLOWED": "true",
        "WEB_VAULT_ENABLED": "false",
        "SMTP_FROM": "",
    })
    env.pop("SMTP_HOST", None)
    log = open(log_path, "w", encoding="utf-8")
    proc = subprocess.Popen([str(BIN)], env=env, stdout=log, stderr=subprocess.STDOUT)
    try:
        wait_alive(proc, Path(log_path))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()
        log.close()


def main():
    if not BIN.is_file():
        raise SystemExit(f"missing {BIN}")
    data = Path(tempfile.mkdtemp(prefix="komboe-migrate-"))
    try:
        boot(data, data / "boot1.log")
        db = next(data.rglob("db.sqlite3"))
        names, versions = tables(db)
        missing = [name for name in NEED if name not in names]
        if missing:
            raise SystemExit(f"migrations did not create {missing}")
        for version in ("20261108000000", "20261108010000"):
            if version not in versions:
                raise SystemExit(f"{version} not in schema migrations: {versions[-8:]}")
        con = sqlite3.connect(db)
        con.execute("INSERT INTO komboe_email_login_policy (user_uuid, interval_secs) VALUES ('kept-user', 60)")
        con.commit()
        con.close()
        backup = data / "db_backup.sqlite3"
        shutil.copy2(db, backup)
        boot(data, data / "boot2.log")
        names2, _ = tables(db)
        if not NEED[0] in names2:
            raise SystemExit("second boot lost the migrated tables")
        con = sqlite3.connect(db)
        kept = con.execute("SELECT interval_secs FROM komboe_email_login_policy WHERE user_uuid='kept-user'").fetchone()
        con.close()
        if kept != (60,):
            raise SystemExit(f"upgrade boot did not keep the row: {kept}")
        # A copy of the upgraded file still opens and has the row. That is the backup the restore command copies back.
        con = sqlite3.connect(backup)
        kept_backup = con.execute(
            "SELECT interval_secs FROM komboe_email_login_policy WHERE user_uuid='kept-user'"
        ).fetchone()
        con.close()
        if kept_backup != (60,):
            raise SystemExit("backup copy lost the migrated row")
        print("MIGRATIONS BOOT PASS", versions[-2:])
    finally:
        shutil.rmtree(data, ignore_errors=True)


if __name__ == "__main__":
    main()
