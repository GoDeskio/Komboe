"""#58 FIDO Credential Exchange (CXF): CLI exports a vault with a passkey to CXF and imports it into another account.

The SDK converts CXF <-> ciphers on the client; the server only stores ciphertext.
Usage: python3 cxf_cli.py [cli-command]  (default: node clients/upstream/apps/cli/build/bw.js)
"""
import base64, importlib.util, json, os, subprocess, sys, tempfile, uuid
from datetime import datetime, timezone
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("ft", os.path.join(HERE, "run.py")); ft = importlib.util.module_from_spec(spec); spec.loader.exec_module(ft)
CLI = sys.argv[1:] or ["node", os.path.join(HERE, "../../clients/upstream/apps/cli/build/bw.js")]
SERVER = os.environ.get("KOMBOE_URL", "https://localhost:8443")

def cli_for(u):
    home = tempfile.mkdtemp()
    env = dict(os.environ, XDG_CONFIG_HOME=home, BITWARDENCLI_APPDATA_DIR=home, NODE_EXTRA_CA_CERTS=os.environ.get("NODE_EXTRA_CA_CERTS", "/workspace/run/tls/cert.pem"), KPW=u.pw, CXFPW="cxf-file-pass-58", BADPW="wrong-pass")
    run = lambda *a: subprocess.run([*CLI, *a], capture_output=True, text=True, timeout=180, env=env)
    run("config", "server", SERVER)
    sess = run("login", u.email, "--passwordenv", "KPW", "--raw").stdout.strip().splitlines()[-1]
    return run, sess

b64u = lambda b: base64.urlsafe_b64encode(b).rstrip(b"=").decode()
key = ec.generate_private_key(ec.SECP256R1())
pkcs8 = b64u(key.private_bytes(serialization.Encoding.DER, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
cred_id = str(uuid.uuid4())

a = ft.User()
fc = [{k: a.e(v) for k, v in dict(credentialId=cred_id, keyType="public-key", keyAlgorithm="ECDSA", keyCurve="P-256", keyValue=pkcs8,
       rpId="cxf.example.test", userHandle=b64u(b"cxf-user-handle"), userName="cxf-user", counter="0", rpName="CXF Test", userDisplayName="CXF User", discoverable="true").items()}
      | {"creationDate": datetime.now(timezone.utc).isoformat()}]
a.api("POST", "/api/ciphers", a.cipher({"name": a.e("cxf-login"), "login": {"username": a.e("cxf-user"), "password": a.e("cxf-secret-58"),
      "uris": [{"uri": a.e("https://cxf.example.test"), "match": None}], "fido2Credentials": fc}}))
a.api("POST", "/api/ciphers", a.cipher({"name": a.e("cxf-note"), "secureNote": {"type": 0}, "notes": a.e("cxf-note-body")}, typ=2))

run, sess = cli_for(a)
out = os.path.join(tempfile.mkdtemp(), "vault.cxf.json")
r = run("export", "--format", "cxf", "--output", out, "--session", sess)
assert r.returncode == 0 and os.path.exists(out), (r.stdout, r.stderr)
doc = json.load(open(out))
text = json.dumps(doc)
assert "cxf.example.test" in text and "cxf-secret-58" in text and "cxf-note-body" in text, text[:500]
assert "passkey" in text, "CXF export must carry the passkey credential"
print("  cxf export: login + passkey + note in CXF JSON")

b = ft.User(); run_b, sess_b = cli_for(b)
r = run_b("import", "cxf", out, "--session", sess_b)
assert r.returncode == 0 and "Imported 2 item" in r.stdout, (r.stdout, r.stderr)
sync = b.api("GET", "/api/sync"); raw = json.dumps(sync)
for plain in ("cxf-secret-58", "cxf.example.test", "cxf-note-body", pkcs8):
    assert plain not in raw, f"plaintext {plain[:12]} reached the server"
ck = lambda c: ft.dec(c["key"], b.uk) if c.get("key") else None
login = next(c for c in sync["ciphers"] if c["type"] == 1); k = ck(login)
assert b.d(login["login"]["password"], k) == "cxf-secret-58"
(f,) = login["login"]["fido2Credentials"]
assert b.d(f["rpId"], k) == "cxf.example.test" and b.d(f["userName"], k) == "cxf-user"
got = base64.urlsafe_b64decode(b.d(f["keyValue"], k) + "==")
assert serialization.load_der_private_key(got, None).private_numbers() == key.private_numbers(), "passkey private key must survive"
note = next(c for c in sync["ciphers"] if c["type"] == 2)
assert b.d(note["notes"], ck(note)) == "cxf-note-body"
print("  cxf import: 2 items, passkey private key intact, server holds ciphertext only")

# Password-protected CXF: sealed on export, opened only with the right password.
enc = out + ".enc.json"
r = run("export", "--format", "cxf", "--password", "cxf-file-pass-58", "--output", enc, "--session", sess)
assert r.returncode == 0 and os.path.exists(enc), (r.stdout, r.stderr)
etext = open(enc).read(); env = json.loads(etext)
assert env["format"] == "komboe-cxf-encrypted" and env["kdf"]["algorithm"] == "argon2id" and env["cipher"] == "aes-256-gcm", env.keys()
for plain in ("cxf-secret-58", "cxf.example.test", "cxf-note-body", "cxf-user"):
    assert plain not in etext, f"plaintext {plain} in encrypted CXF"
c = ft.User(); run_c, sess_c = cli_for(c)
r = run_c("import", "cxf", enc, "--session", sess_c)
assert r.returncode != 0 and "password protected" in (r.stdout + r.stderr), (r.stdout, r.stderr)
r = run_c("import", "cxf", enc, "--passwordenv", "BADPW", "--session", sess_c)
assert r.returncode != 0 and "Invalid file password" in (r.stdout + r.stderr), (r.stdout, r.stderr)
r = run_c("import", "cxf", enc, "--passwordenv", "CXFPW", "--session", sess_c)
assert r.returncode == 0 and "Imported 2 item" in r.stdout, (r.stdout, r.stderr)
csync = c.api("GET", "/api/sync")
assert all(x["name"].startswith("2.") for x in csync["ciphers"]) and "cxf-secret-58" not in json.dumps(csync)
print("  encrypted cxf: Argon2id+AES-GCM file, no plaintext, wrong/missing password refused, right password imports 2 items")
print("CXF CLI PASS")
