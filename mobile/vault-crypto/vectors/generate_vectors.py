#!/usr/bin/env python3
"""Independent vault-crypto vectors.

The numbers come from the public Bitwarden protocol (PBKDF2-HMAC-SHA256,
HKDF-Expand SHA-256 with info "enc"/"mac", AES-256-CBC + HMAC-SHA256,
Argon2id, RSA-OAEP) and are checked against Node's WebCrypto / OpenSSL
primitives, which are what the web vault uses for these operations. Nothing
here is taken from the Bitwarden SDK.
"""
import base64
import hashlib
import hmac
import json
import pathlib
import subprocess
import textwrap

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
import argon2.low_level as argon2

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "src" / "test" / "resources" / "vectors.json"


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def hkdf_expand(prk: bytes, info: bytes, length: int) -> bytes:
    """RFC 5869 HKDF-Expand, SHA-256. PRK is already extracted (the KDF output)."""
    hash_len = 32
    n = (length + hash_len - 1) // hash_len
    okm = b""
    previous = b""
    for i in range(1, n + 1):
        previous = hmac.new(prk, previous + info + bytes([i]), hashlib.sha256).digest()
        okm += previous
    return okm[:length]


def aes_cbc_encrypt(key: bytes, iv: bytes, plain: bytes) -> bytes:
    pad = 16 - (len(plain) % 16)
    padded = plain + bytes([pad]) * pad
    encryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    return encryptor.update(padded) + encryptor.finalize()


def encstring_type2(enc_key: bytes, mac_key: bytes, iv: bytes, plain: bytes) -> str:
    ct = aes_cbc_encrypt(enc_key, iv, plain)
    mac = hmac.new(mac_key, iv + ct, hashlib.sha256).digest()
    return f"2.{b64(iv)}|{b64(ct)}|{b64(mac)}"


def node_check(master: bytes, enc: bytes, mac: bytes, iv: bytes, ct: bytes, mac_bytes: bytes, password_hash: str) -> None:
    """Confirm the stretch, MAC and password hash with Node, the web vault's runtime."""
    script = textwrap.dedent(
        f"""
        const crypto = require('crypto');
        const prk = Buffer.from({json.dumps(master.hex())}, 'hex');
        function expand(info, len) {{
          const infoB = Buffer.from(info, 'utf8');
          let prev = Buffer.alloc(0);
          let okm = Buffer.alloc(0);
          const n = Math.ceil(len / 32);
          for (let i = 1; i <= n; i++) {{
            prev = crypto.createHmac('sha256', prk).update(prev).update(infoB).update(Buffer.from([i])).digest();
            okm = Buffer.concat([okm, prev]);
          }}
          return okm.subarray(0, len);
        }}
        const enc = expand('enc', 32);
        const mac = expand('mac', 32);
        const expectEnc = Buffer.from({json.dumps(enc.hex())}, 'hex');
        const expectMac = Buffer.from({json.dumps(mac.hex())}, 'hex');
        if (!enc.equals(expectEnc) || !mac.equals(expectMac)) {{
          console.error('hkdf mismatch');
          process.exit(1);
        }}
        const iv = Buffer.from({json.dumps(iv.hex())}, 'hex');
        const ct = Buffer.from({json.dumps(ct.hex())}, 'hex');
        const tag = crypto.createHmac('sha256', mac).update(iv).update(ct).digest();
        const expectTag = Buffer.from({json.dumps(mac_bytes.hex())}, 'hex');
        if (!tag.equals(expectTag)) {{
          console.error('mac mismatch');
          process.exit(1);
        }}
        const pw = Buffer.from('correct horse battery staple', 'utf8');
        const hashed = crypto.pbkdf2Sync(prk, pw, 1, 32, 'sha256');
        if (hashed.toString('base64') !== {json.dumps(password_hash)}) {{
          console.error('password hash mismatch', hashed.toString('base64'));
          process.exit(1);
        }}
        console.log('node-webcrypto-primitives-ok');
        """
    )
    proc = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    if "node-webcrypto-primitives-ok" not in proc.stdout:
        raise SystemExit(proc.stdout + proc.stderr)


def main() -> None:
    email = "ada@komboe.test"
    password = "correct horse battery staple"
    iterations = 1000  # small on purpose; the algorithm is the same at 600000
    salt = email.encode("utf-8")
    master = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations, 32)
    enc = hkdf_expand(master, b"enc", 32)
    mac = hkdf_expand(master, b"mac", 32)
    password_hash = b64(hashlib.pbkdf2_hmac("sha256", master, password.encode("utf-8"), 1, 32))
    local_hash = b64(hashlib.pbkdf2_hmac("sha256", master, password.encode("utf-8"), 2, 32))

    iv = bytes(range(16))
    plain = b"komboe vault item"
    ct = aes_cbc_encrypt(enc, iv, plain)
    mac_bytes = hmac.new(mac, iv + ct, hashlib.sha256).digest()
    enc_string = encstring_type2(enc, mac, iv, plain)
    node_check(master, enc, mac, iv, ct, mac_bytes, password_hash)

    # A second field, encrypted under a random-looking 64-byte item key (fixed).
    item_key = hashlib.sha512(b"komboe-item-key").digest()  # 64 bytes
    item_iv = bytes(range(16, 32))
    secret = "p@ssw0rd-vector"
    item_enc = encstring_type2(item_key[:32], item_key[32:], item_iv, secret.encode("utf-8"))

    argon_memory_mib = 8
    argon_iters = 1
    argon_par = 1
    argon = argon2.hash_secret_raw(
        secret=password.encode("utf-8"),
        salt=salt,
        time_cost=argon_iters,
        memory_cost=argon_memory_mib * 1024,
        parallelism=argon_par,
        hash_len=32,
        type=argon2.Type.ID,
        version=19,
    )

    # RSA-OAEP SHA-1 (EncString type 4) and SHA-256 (type 3) of a 64-byte key.
    rsa_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    org_key = hashlib.sha512(b"komboe-org-key").digest()
    sha1_ct = rsa_key.public_key().encrypt(
        org_key,
        padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA1()), algorithm=hashes.SHA1(), label=None),
    )
    sha256_ct = rsa_key.public_key().encrypt(
        org_key,
        padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None),
    )
    pem = rsa_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode("ascii")

    # Send: 16-byte material, HKDF(salt="bitwarden-send", info="send") -> 64 byte key.
    material = bytes(range(16))
    prk = hmac.new(b"bitwarden-send", material, hashlib.sha256).digest()
    send_key = hkdf_expand(prk, b"send", 64)
    send_name = encstring_type2(send_key[:32], send_key[32:], bytes([7]) * 16, b"Quarterly report")
    send_password_hash = b64(hashlib.pbkdf2_hmac("sha256", material, b"send-secret", 100000, 32))

    # TOTP RFC 6238 appendix B, 8-byte secret "12345678901234567890", SHA1, T0=59, 8 digits.
    totp_secret = b"12345678901234567890"
    vectors = {
        "pbkdf2": {
            "email": email,
            "password": password,
            "iterations": iterations,
            "masterKey": b64(master),
            "encKey": b64(enc),
            "macKey": b64(mac),
            "serverPasswordHash": password_hash,
            "localPasswordHash": local_hash,
        },
        "encString": {
            "iv": b64(iv),
            "plaintext": plain.decode("ascii"),
            "ciphertext": enc_string,
        },
        "item": {
            "key": b64(item_key),
            "iv": b64(item_iv),
            "plaintext": secret,
            "ciphertext": item_enc,
        },
        "argon2id": {
            "email": email,
            "password": password,
            "iterations": argon_iters,
            "memoryMiB": argon_memory_mib,
            "parallelism": argon_par,
            "masterKey": b64(argon),
        },
        "rsa": {
            "pkcs8Pem": pem,
            "orgKey": b64(org_key),
            "type4": "4." + b64(sha1_ct),
            "type3": "3." + b64(sha256_ct),
        },
        "send": {
            "material": b64(material),
            "derivedKey": b64(send_key),
            "iv": b64(bytes([7]) * 16),
            "name": "Quarterly report",
            "nameEnc": send_name,
            "password": "send-secret",
            "passwordHash": send_password_hash,
        },
        "totp": {
            "secretAscii": totp_secret.decode("ascii"),
            "time": 59,
            "period": 30,
            "digits": 8,
            "algorithm": "SHA1",
            "code": "94287082",
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(vectors, indent=2) + "\n")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
