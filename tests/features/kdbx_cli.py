"""#77 KeePass KDBX: CLI imports a .kdbx (SDK) and exports a password-protected KDBX 4 file.

Server only ever sees encrypted ciphers; the kdbx is built and read on the client.
Usage: python3 kdbx_cli.py [cli-command]  (default: node clients/upstream/apps/cli/build/bw.js)
Needs: node (kdbxweb from clients node_modules) and pykeepass (KOMBOE_KPVENV python) as independent readers.
"""
import importlib.util, json, os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
CLIENTS = os.path.join(HERE, "../../clients/upstream")
spec = importlib.util.spec_from_file_location("ft", os.path.join(HERE, "run.py")); ft = importlib.util.module_from_spec(spec); spec.loader.exec_module(ft)
CLI = sys.argv[1:] or ["node", os.path.join(CLIENTS, "apps/cli/build/bw.js")]
KPPY = os.environ.get("KOMBOE_KPVENV_PY", "/workspace/run/kpvenv/bin/python")
SERVER = os.environ.get("KOMBOE_CLI_URL", "https://localhost:8443")  # CLI production builds refuse http
d = tempfile.mkdtemp()

# 1. Build a source KeePass DB with kdbxweb (independent of the SDK reader).
mk = os.path.join(d, "mk.cjs")
open(mk, "w").write(r"""
const kdbxweb = require('kdbxweb'); const { argon2d, argon2id } = require('hash-wasm'); const fs = require('fs');
kdbxweb.CryptoEngine.setArgon2Impl(async (p, s, m, i, l, par, t) => { const o = await (t === 2 ? argon2id : argon2d)({password: new Uint8Array(p), salt: new Uint8Array(s), memorySize: m, iterations: i, hashLength: l, parallelism: par, outputType: 'binary'}); return o.buffer.slice(o.byteOffset, o.byteOffset + o.byteLength); });
(async () => {
const db = kdbxweb.Kdbx.create(new kdbxweb.Credentials(kdbxweb.ProtectedValue.fromString('kdbx-pass-77')), 'src');
const g = db.createGroup(db.getDefaultGroup(), 'Servers');
const e = db.createEntry(g);
e.fields.set('Title', 'kdbx-entry'); e.fields.set('UserName', 'kdbx-user');
e.fields.set('Password', kdbxweb.ProtectedValue.fromString('kdbx-secret-77'));
e.fields.set('URL', 'https://kdbx.example.test'); e.fields.set('Notes', 'kdbx-notes');
e.fields.set('API_TOKEN', kdbxweb.ProtectedValue.fromString('tok-77'));
fs.writeFileSync(process.argv[2], Buffer.from(await db.save()));
})();
""")
src = os.path.join(d, "src.kdbx")
subprocess.run(["node", mk, src], check=True, env=dict(os.environ, NODE_PATH=os.path.join(CLIENTS, "node_modules")))

def cli_for(u):
    home = tempfile.mkdtemp()
    env = dict(os.environ, XDG_CONFIG_HOME=home, BITWARDENCLI_APPDATA_DIR=home, NODE_EXTRA_CA_CERTS=os.environ.get("NODE_EXTRA_CA_CERTS", "/workspace/run/tls/cert.pem"), KPW=u.pw, KDBXPW="kdbx-pass-77", EXPPW="export-pass-77")
    run = lambda *a: subprocess.run([*CLI, *a], capture_output=True, text=True, timeout=180, env=env)
    run("config", "server", SERVER)
    sess = run("login", u.email, "--passwordenv", "KPW", "--raw").stdout.strip().splitlines()[-1]
    return run, sess

# 2. Import into user A via the CLI (SDK parses, encrypts and submits).
a = ft.User(); run, sess = cli_for(a)
r = run("import", "keepasskdbx", src, "--passwordenv", "KDBXPW", "--session", sess)
assert r.returncode == 0 and "Imported 1 item" in r.stdout, (r.stdout, r.stderr)
bad = run("import", "keepasskdbx", src, "--passwordenv", "KPW", "--session", sess)
assert bad.returncode != 0, "wrong kdbx password must fail"
sync = a.api("GET", "/api/sync")
(c,) = sync["ciphers"]
assert c["name"].startswith("2.") and c["login"]["password"].startswith("2."), "server must hold ciphertext only"
raw = json.dumps(sync)
for plain in ("kdbx-secret-77", "tok-77", "kdbx-user", "kdbx-entry"):
    assert plain not in raw, f"plaintext {plain} reached the server"
k = ft.dec(c["key"], a.uk) if c.get("key") else None
assert a.d(c["login"]["password"], k) == "kdbx-secret-77"
f = {a.d(x["name"], k): (a.d(x["value"], k), x["type"]) for x in c["fields"]}
assert f["API_TOKEN"] == ("tok-77", 1), f  # protected KeePass field -> hidden custom field
print("  kdbx import: 1 item, encrypted at rest, protected field hidden")

# 3. Export as KDBX 4 and read it with pykeepass (independent implementation).
out = os.path.join(d, "out.kdbx")
r = run("export", "--format", "kdbx", "--password", "export-pass-77", "--output", out, "--session", sess)
assert r.returncode == 0 and os.path.getsize(out) > 0, (r.stdout, r.stderr)
assert open(out, "rb").read(4) == bytes.fromhex("03d9a29a"), "KeePass signature"
chk = subprocess.run([KPPY, "-c", """
import sys, json
from pykeepass import PyKeePass
k = PyKeePass(sys.argv[1], password='export-pass-77')
e = k.find_entries(title='kdbx-entry', first=True)
print(json.dumps({'v': list(k.version), 'u': e.username, 'p': e.password, 'url': e.url, 'n': e.notes, 'tok': e.custom_properties.get('API_TOKEN'), 'prot': e.is_custom_property_protected('API_TOKEN')}))
""", out], capture_output=True, text=True)
assert chk.returncode == 0, chk.stderr
got = json.loads(chk.stdout)
assert got == {"v": [4, 0], "u": "kdbx-user", "p": "kdbx-secret-77", "url": "https://kdbx.example.test", "n": "kdbx-notes", "tok": "tok-77", "prot": True}, got
wrong = subprocess.run([KPPY, "-c", "import sys\nfrom pykeepass import PyKeePass\nPyKeePass(sys.argv[1], password='nope')", out], capture_output=True)
assert wrong.returncode != 0, "export must be password protected"
print("  kdbx export: KDBX 4, readable by pykeepass, protected field kept protected, wrong password rejected")

# 4. Round trip: the exported file imports into another account.
b = ft.User(); run_b, sess_b = cli_for(b)
r = run_b("import", "keepasskdbx", out, "--passwordenv", "EXPPW", "--session", sess_b)
assert r.returncode == 0 and "Imported 1 item" in r.stdout, (r.stdout, r.stderr)
print("  round trip: exported kdbx re-imports")

# 5. A KDBX 4 file written by pykeepass (KeePass reference format, Argon2) imports.
pk = os.path.join(d, "pykeepass.kdbx")
mk = subprocess.run([KPPY, "-c", """
import sys
from pykeepass import create_database
k = create_database(sys.argv[1], password='pk-pass-77')
g = k.add_group(k.root_group, 'Work')
e = k.add_entry(g, 'pk-entry', 'pk-user', 'pk-secret-77', url='https://pk.example.test', notes='pk-notes')
e.set_custom_property('PK_TOKEN', 'pk-tok-77', protect=True)
k.add_entry(k.root_group, 'pk-root', 'root-user', 'root-pass-77')
k.save()
print(list(k.version), k.kdf_algorithm)
""", pk], capture_output=True, text=True)
assert mk.returncode == 0 and mk.stdout.startswith("[4, "), (mk.stdout, mk.stderr)
os.environ["PKPW"] = "pk-pass-77"
c = ft.User(); run_c, sess_c = cli_for(c)
r = run_c("import", "keepasskdbx", pk, "--passwordenv", "PKPW", "--session", sess_c)
assert r.returncode == 0 and "Imported 2 item(s)" in r.stdout, (r.stdout, r.stderr)
sync = c.api("GET", "/api/sync"); raw = json.dumps(sync)
for plain in ("pk-secret-77", "pk-tok-77", "pk-user", "root-pass-77", "pk-entry"):
    assert plain not in raw, f"plaintext {plain} reached the server"
byname = {}
for x in sync["ciphers"]:
    kx = ft.dec(x["key"], c.uk) if x.get("key") else None
    byname[c.d(x["name"], kx)] = (x, kx)
assert set(byname) == {"pk-entry", "pk-root"}, set(byname)
e, ke = byname["pk-entry"]
assert c.d(e["login"]["password"], ke) == "pk-secret-77" and c.d(e["login"]["username"], ke) == "pk-user"
assert c.d(e["notes"], ke) == "pk-notes"
f = {c.d(x["name"], ke): (c.d(x["value"], ke), x["type"]) for x in e["fields"]}
assert f.get("PK_TOKEN") == ("pk-tok-77", 1), f
print("  pykeepass KDBX 4 (%s) import: 2 items, protected field hidden, encrypted at rest" % mk.stdout.split()[-1])
print("KDBX CLI PASS")
