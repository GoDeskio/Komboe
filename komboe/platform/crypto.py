"""Client-compatible vault crypto.

AES-256-CBC + HMAC-SHA256 EncStrings (type 2) and PBKDF2-SHA256, matching
tests/e2e/roundtrip.py. The server stores the results; it does not need the
master password to use this module. Local-only and test clients do.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re

from cryptography.hazmat.primitives import hashes, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.hkdf import HKDFExpand

CIPHERTEXT_RE = re.compile(r"^2\.[A-Za-z0-9+/]+=*\|[A-Za-z0-9+/]+=*\|[A-Za-z0-9+/]+=*$")

b64 = lambda b: base64.b64encode(b).decode()
ub64 = base64.b64decode


def stretch(key: bytes) -> bytes:
    """HKDF-Expand(SHA-256) of a 32-byte master key into enc||mac."""
    expand = lambda info: HKDFExpand(hashes.SHA256(), 32, info).derive(key)
    return expand(b"enc") + expand(b"mac")


def enc(plain: bytes, key64: bytes) -> str:
    ek, mk, iv = key64[:32], key64[32:], os.urandom(16)
    padder = padding.PKCS7(128).padder()
    data = padder.update(plain) + padder.finalize()
    encryptor = Cipher(algorithms.AES(ek), modes.CBC(iv)).encryptor()
    ct = encryptor.update(data) + encryptor.finalize()
    mac = hmac.new(mk, iv + ct, hashlib.sha256).digest()
    return f"2.{b64(iv)}|{b64(ct)}|{b64(mac)}"


def dec(token: str, key64: bytes) -> bytes:
    kind, rest = token.split(".", 1)
    if kind != "2":
        raise ValueError(f"unsupported ciphertext type {kind}")
    iv, ct, mac = map(ub64, rest.split("|"))
    expect = hmac.new(key64[32:], iv + ct, hashlib.sha256).digest()
    if not hmac.compare_digest(mac, expect):
        raise ValueError("MAC mismatch")
    decryptor = Cipher(algorithms.AES(key64[:32]), modes.CBC(iv)).decryptor()
    data = decryptor.update(ct) + decryptor.finalize()
    unpadder = padding.PKCS7(128).unpadder()
    return unpadder.update(data) + unpadder.finalize()


def is_ciphertext(value: object) -> bool:
    return isinstance(value, str) and bool(CIPHERTEXT_RE.match(value))


def is_pgp_message(value: object) -> bool:
    return isinstance(value, str) and value.startswith("-----BEGIN PGP MESSAGE-----") and "-----END PGP MESSAGE-----" in value


def is_sealed(value: object) -> bool:
    """Ciphertext the server is allowed to store: AES EncString or an OpenPGP message."""
    return is_ciphertext(value) or is_pgp_message(value)


def master_key(password: str, email: str, iterations: int = 600_000) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), email.encode(), iterations, 32)


def password_hash(master: bytes, password: str) -> str:
    return b64(hashlib.pbkdf2_hmac("sha256", master, password.encode(), 1, 32))


def enc_str(text: str, key64: bytes) -> str:
    return enc(text.encode(), key64)


def dec_str(token: str, key64: bytes) -> str:
    return dec(token, key64).decode()
