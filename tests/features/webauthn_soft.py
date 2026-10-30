"""Minimal software WebAuthn authenticator (P-256, attestation "none") for server-side 2FA tests. Test-only."""
import base64, hashlib, json, os, struct
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes

def b64u(b): return base64.urlsafe_b64encode(b).rstrip(b"=").decode()
def ub64u(s): return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))

def cbor(v):
    def head(major, n):
        if n < 24: return bytes([major << 5 | n])
        for ai, fmt in ((24, ">B"), (25, ">H"), (26, ">I"), (27, ">Q")):
            if n < 1 << (8 * struct.calcsize(fmt)): return bytes([major << 5 | ai]) + struct.pack(fmt, n)
    if isinstance(v, bool): return b"\xf5" if v else b"\xf4"
    if isinstance(v, int): return head(0, v) if v >= 0 else head(1, -1 - v)
    if isinstance(v, bytes): return head(2, len(v)) + v
    if isinstance(v, str): b = v.encode(); return head(3, len(b)) + b
    if isinstance(v, list): return head(4, len(v)) + b"".join(cbor(x) for x in v)
    if isinstance(v, dict): return head(5, len(v)) + b"".join(cbor(k) + cbor(x) for k, x in v.items())
    raise TypeError(type(v))

class SoftAuthenticator:
    def __init__(self, origin):
        self.origin = origin; self.key = ec.generate_private_key(ec.SECP256R1()); self.cred = os.urandom(32); self.count = 0
    def _cd(self, typ, challenge): return json.dumps({"type": typ, "challenge": challenge, "origin": self.origin, "crossOrigin": False}).encode()
    def create(self, options):
        rp = options["rp"]["id"]; n = self.key.public_key().public_numbers()
        cose = cbor({1: 2, 3: -7, -1: 1, -2: n.x.to_bytes(32, "big"), -3: n.y.to_bytes(32, "big")})
        auth = hashlib.sha256(rp.encode()).digest() + b"\x41" + struct.pack(">I", 0) + b"\0" * 16 + struct.pack(">H", len(self.cred)) + self.cred + cose
        cd = self._cd("webauthn.create", options["challenge"])
        return {"id": b64u(self.cred), "rawId": b64u(self.cred), "type": "public-key",
                "response": {"attestationObject": b64u(cbor({"fmt": "none", "attStmt": {}, "authData": auth})), "clientDataJSON": b64u(cd)}}
    def get(self, options):
        rp = options.get("rpId") or options["rp_id"]; self.count += 1
        auth = hashlib.sha256(rp.encode()).digest() + b"\x01" + struct.pack(">I", self.count)
        cd = self._cd("webauthn.get", options["challenge"])
        sig = self.key.sign(auth + hashlib.sha256(cd).digest(), ec.ECDSA(hashes.SHA256()))
        return {"id": b64u(self.cred), "rawId": b64u(self.cred), "type": "public-key", "extensions": {},
                "response": {"authenticatorData": b64u(auth), "clientDataJSON": b64u(cd), "signature": b64u(sig), "userHandle": None}}
