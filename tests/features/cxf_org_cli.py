"""#58 CXF organization-vault export: an org owner exports only that org's items to CXF
(plain and password-protected); a plain member and a non-member are refused.

The org key is unwrapped on the client; the server only ever sees ciphertext.
Usage: python3 cxf_org_cli.py [cli-command]  (default: node clients/upstream/apps/cli/build/bw.js)
"""
import importlib.util, json, os, re, sys, tempfile, urllib.parse
from cryptography.hazmat.primitives.serialization import load_der_public_key

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("ft", os.path.join(HERE, "run.py")); ft = importlib.util.module_from_spec(spec); spec.loader.exec_module(ft)
CLI = sys.argv[1:] or ["node", os.path.join(HERE, "../../clients/upstream/apps/cli/build/bw.js")]
SERVER = os.environ.get("KOMBOE_CLI_URL", "https://localhost:8443")  # CLI production builds refuse http

def cli_for(u):
    import subprocess
    home = tempfile.mkdtemp()
    env = dict(os.environ, XDG_CONFIG_HOME=home, BITWARDENCLI_APPDATA_DIR=home, NODE_EXTRA_CA_CERTS=os.environ.get("NODE_EXTRA_CA_CERTS", "/workspace/run/tls/cert.pem"), KPW=u.pw, CXFPW="cxf-org-pass-58")
    run = lambda *a: subprocess.run([*CLI, *a], capture_output=True, text=True, timeout=180, env=env)
    run("config", "server", SERVER)
    sess = run("login", u.email, "--passwordenv", "KPW", "--raw").stdout.strip().splitlines()[-1]
    return run, sess

owner = ft.a(); oid, ok, oaep = ft.org(); col = ft.S["col"]
owner.api("POST", "/api/ciphers/create", {"cipher": owner.cipher({"name": owner.e("org-cxf-item", ok), "login": {"username": owner.e("org-user", ok),
          "password": owner.e("org-secret-58", ok), "uris": [{"uri": owner.e("https://org.example.test", ok), "match": None}]}}, key=ok, org=oid), "collectionIds": [col]})
owner.api("POST", "/api/ciphers", owner.cipher({"name": owner.e("personal-cxf-item"), "login": {"username": owner.e("me"), "password": owner.e("personal-secret-58"), "uris": []}}))

run, sess = cli_for(owner)
d = tempfile.mkdtemp(); out = os.path.join(d, "org.cxf.json")
r = run("export", "--format", "cxf", "--organizationid", oid, "--output", out, "--session", sess)
assert r.returncode == 0 and os.path.exists(out), (r.stdout, r.stderr)
text = open(out).read()
assert "org-cxf-item" in text and "org-secret-58" in text and "org.example.test" in text, text[:400]
assert "personal-cxf-item" not in text and "personal-secret-58" not in text, "org export must not include personal items"
print("  owner org export: org item only, personal vault excluded")

enc_out = os.path.join(d, "org.cxf.enc.json")
r = run("export", "--format", "cxf", "--organizationid", oid, "--password", "cxf-org-pass-58", "--output", enc_out, "--session", sess)
assert r.returncode == 0, (r.stdout, r.stderr)
raw = open(enc_out).read(); assert json.loads(raw)["format"] == "komboe-cxf-encrypted" and "org-secret-58" not in raw and "org-cxf-item" not in raw
imp = ft.User(); run_i, sess_i = cli_for(imp)
r = run_i("import", "cxf", out, "--session", sess_i)
assert r.returncode == 0 and "Imported 1 item" in r.stdout, (r.stdout, r.stderr)
assert "org-secret-58" not in json.dumps(imp.api("GET", "/api/sync")), "re-import must reach the server as ciphertext"
print("  org CXF re-imports into another account (ciphertext only on the server)")
print("  owner org export --password: encrypted envelope, no plaintext")

# Plain member (type 2 = User): can read the org item but has no export permission.
v = ft.b()
owner.api("POST", f"/api/organizations/{oid}/users/invite", {"emails": [v.email], "type": 2, "collections": [{"id": col, "readOnly": True, "hidePasswords": False, "manage": False}], "accessAll": False, "permissions": {}, "groups": []})
mem = next(m for m in owner.api("GET", f"/api/organizations/{oid}/users")["data"] if m["email"] == v.email)
if mem["status"] == 0:
    tok = urllib.parse.unquote(re.search(r"token=([^&\"'\s<]+)", ft.mailpit(v.email, "Join")["Text"]).group(1)) if os.environ.get("KOMBOE_SMTP") else ""
    v.api("POST", f"/api/organizations/{oid}/users/{mem['id']}/accept", {"token": tok, "resetPasswordKey": None})
pk = owner.api("GET", f"/api/users/{v.id}/public-key")["publicKey"]
owner.api("POST", f"/api/organizations/{oid}/users/{mem['id']}/confirm", {"key": "4." + ft.b64(load_der_public_key(ft.ub64(pk)).encrypt(ok, oaep))})
run_v, sess_v = cli_for(v)
r = run_v("export", "--format", "cxf", "--organizationid", oid, "--output", os.path.join(d, "member.json"), "--session", sess_v)
assert r.returncode != 0 and "permission" in (r.stdout + r.stderr), (r.stdout, r.stderr)
assert not os.path.exists(os.path.join(d, "member.json"))
print("  plain member refused (no export permission)")

stranger = ft.User(); run_s, sess_s = cli_for(stranger)
r = run_s("export", "--format", "cxf", "--organizationid", oid, "--output", os.path.join(d, "s.json"), "--session", sess_s)
assert r.returncode != 0 and "not a member" in (r.stdout + r.stderr), (r.stdout, r.stderr)
print("  non-member refused")
print("CXF ORG CLI PASS")
