"""OpenPGP helpers via the system gpg binary. Private keys stay in the caller's GNUPGHOME."""
from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path


class GpgError(Exception):
    pass


def _run(args: list[str], env: dict, data: bytes | None = None) -> subprocess.CompletedProcess:
    proc = subprocess.run(args, input=data, env=env, capture_output=True)
    if proc.returncode != 0:
        raise GpgError(proc.stderr.decode(errors="replace")[:500])
    return proc


def _home(pub_armored: str) -> tuple[str, dict, str]:
    home = tempfile.mkdtemp(prefix="komboe-gpg-")
    os.chmod(home, 0o700)
    env = dict(os.environ, GNUPGHOME=home)
    _run(["gpg", "--batch", "--import"], env, pub_armored.encode())
    listed = _run(["gpg", "--batch", "--list-keys", "--with-colons"], env).stdout.decode()
    fpr = next(line.split(":")[9] for line in listed.splitlines() if line.startswith("fpr:"))
    return home, env, fpr


def encrypt(pub_armored: str, plaintext: bytes) -> str:
    _home_dir, env, fpr = _home(pub_armored)
    out = _run(
        ["gpg", "--batch", "--trust-model", "always", "--encrypt", "--armor", "--recipient", fpr],
        env, plaintext,
    )
    return out.stdout.decode()


def verify(pub_armored: str, nonce: bytes, signature: str) -> None:
    _home_dir, env, _fpr = _home(pub_armored)
    directory = Path(_home_dir)
    nonce_path = directory / "nonce"
    sig_path = directory / "nonce.asc"
    nonce_path.write_bytes(nonce)
    sig_path.write_text(signature)
    _run(["gpg", "--batch", "--verify", str(sig_path), str(nonce_path)], env)


def public_only(armored: str) -> bool:
    return "BEGIN PGP PUBLIC KEY BLOCK" in armored and "PRIVATE KEY BLOCK" not in armored
