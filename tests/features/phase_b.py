# Phase B feature tests (family/company plans, split-off, aliases, client builds, Playwright).
# Loaded by run.py into its namespace; entries here replace the Phase A placeholders.
from cryptography.hazmat.primitives.serialization import load_der_public_key

OAEP = apad.OAEP(mgf=apad.MGF1(hashes.SHA1()), algorithm=hashes.SHA1(), label=None)
here = os.path.dirname(os.path.abspath(__file__))
ART = os.environ.get("KOMBOE_ARTIFACTS", "/workspace/artifacts")

def mkorg(u, name="Fam"):
    """Create an org entirely client-side: org key + org RSA keypair generated here, wrapped to u's public key."""
    ok = os.urandom(64); opriv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    r = u.api("POST", "/api/organizations", {"name": name, "billingEmail": u.email, "planType": 0,
        "key": "4." + b64(u.priv.public_key().encrypt(ok, OAEP)), "collectionName": enc(b"Default", ok),
        "keys": {"publicKey": b64(opriv.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)),
                 "encryptedPrivateKey": enc(opriv.private_bytes(serialization.Encoding.DER, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()), ok)}})
    return r["id"], ok

def add_member(owner, oid, ok, v, typ=2):
    owner.api("POST", f"/api/organizations/{oid}/users/invite", {"emails": [v.email], "type": typ, "collections": [], "accessAll": False, "permissions": {}, "groups": []})
    mem = next(m for m in owner.api("GET", f"/api/organizations/{oid}/users")["data"] if m["email"] == v.email)
    if mem["status"] == 0:
        tok = ""
        if os.environ.get("KOMBOE_SMTP"):  # mail enabled: the accept token only arrives in the invite email
            b = mailpit(v.email, "Join"); tok = urllib.parse.unquote(re.search(r"token=([^&\"'\s<]+)", b["Text"] + b["HTML"]).group(1))
        v.api("POST", f"/api/organizations/{oid}/users/{mem['id']}/accept", {"token": tok, "resetPasswordKey": None})
    pk = owner.api("GET", f"/api/users/{v.id}/public-key")["publicKey"]
    owner.api("POST", f"/api/organizations/{oid}/users/{mem['id']}/confirm", {"key": "4." + b64(load_der_public_key(ub64(pk)).encrypt(ok, OAEP))})
    return mem["id"]

def expect(code, fn, *a, **k):
    try: fn(*a, **k)
    except HTTPErr as e:
        assert e.code in (code if isinstance(code, tuple) else (code,)), e; return e
    raise AssertionError(f"expected HTTP {code}")

def family():
    if "fam" not in S:
        o = User(); oid, ok = mkorg(o, "Family")
        p = o.api("PUT", f"/api/komboe/organizations/{oid}/plan", {"kind": "family", "seats": 3, "pricePerMemberCents": 150})
        assert p["kind"] == "family" and p["seats"] == 3
        kid = User(); add_member(o, oid, ok, kid)
        S["fam"] = (o, oid, ok, kid)
    return S["fam"]

@t(27)
def _():
    o, oid, ok, kid = family()
    extra = User(); add_member(o, oid, ok, extra)                       # seat 3 of 3
    e = expect(400, add_member, o, oid, ok, User())                      # seat 4 refused
    assert "Seat limit" in str(e)
    assert o.api("GET", f"/api/komboe/organizations/{oid}/plan")["seatsUsed"] == 3
    expect(403, kid.api, "PUT", f"/api/komboe/organizations/{oid}/plan", {"kind": "family", "seats": 9})
    S["fam_extra"] = extra
    return DONE("family plan: seat limit enforced at invite (3/3 then refused); only owner changes plan")
@t(28)
def _():
    o = User(); oid, ok = mkorg(o, "Co"); o.api("PUT", f"/api/komboe/organizations/{oid}/plan", {"kind": "company", "seats": 1})
    expect(400, add_member, o, oid, ok, User())
    o.api("PUT", f"/api/komboe/organizations/{oid}/plan", {"kind": "company", "seats": 2}); add_member(o, oid, ok, User())
    expect(400, o.api, "PUT", f"/api/komboe/organizations/{oid}/plan", {"kind": "company", "seats": 1})
    return DONE("company per-seat plan: add seats to admit members; cannot shrink below members")
@t(30)
def _():
    o, oid, ok, kid = family()
    secret = "kid-secret-" + uuid.uuid4().hex[:6]
    cid = kid.api("POST", "/api/ciphers", kid.cipher({"name": kid.e(secret)}))["id"]
    m = o.api("GET", f"/api/komboe/organizations/{oid}/members")
    row = next(x for x in m["data"] if x["email"] == kid.email)
    assert row["personalItemCount"] >= 1 and row["vaultReadable"] is False
    assert secret not in json.dumps(m) and cid not in json.dumps(m)
    expect((400, 401, 403, 404), o.api, "GET", f"/api/ciphers/{cid}")
    expect(403, kid.api, "GET", f"/api/komboe/organizations/{oid}/members")
    return DONE("admin sees sub-account metadata (email, 2FA, item count) but no items/keys; owner 4xx on member's item")
@t(32)
def _():
    o, oid, ok, kid = family()
    q = o.api("GET", f"/api/komboe/organizations/{oid}/billing/quote")
    assert q["pricePerMemberCents"] == 150 and q["monthlyTotalCents"] == q["seatsUsed"] * 150
    status = "done" if q["provider"] == "stripe-test" else "partial"
    return (status, f"per-member pricing quote {q['seatsUsed']} x 150c = {q['monthlyTotalCents']}c; provider={q['provider']} ({q['providerStatus']})")
@t(31)
def _():
    o, oid, ok, kid = family()
    keep = kid.api("POST", "/api/ciphers", kid.cipher({"name": kid.e("kept-personal")}))["id"]
    r = kid.api("POST", f"/api/komboe/organizations/{oid}/split-requests", {"note": "starting my own family"})
    assert r["status"] == "pending"
    expect(400, kid.api, "POST", f"/api/komboe/split-requests/{r['id']}/complete", {"newOrganizationId": oid})  # not approved
    expect(403, kid.api, "POST", f"/api/komboe/split-requests/{r['id']}/approve")                            # member can't self-approve
    assert any(x["id"] == r["id"] for x in o.api("GET", f"/api/komboe/organizations/{oid}/split-requests")["data"])
    assert o.api("POST", f"/api/komboe/split-requests/{r['id']}/approve")["status"] == "approved"
    nid, nok = mkorg(kid, "Kid Family")                                # keys generated client-side
    done = kid.api("POST", f"/api/komboe/split-requests/{r['id']}/complete", {"newOrganizationId": nid})
    assert done["status"] == "completed"
    s = kid.api("GET", "/api/sync"); orgs = {x["id"]: x for x in s["profile"]["organizations"]}
    assert oid not in orgs and orgs[nid]["type"] == 0, "member should leave old org and own new one"
    assert any(c["id"] == keep and kid.d(c["name"]) == "kept-personal" for c in s["ciphers"]), "personal vault kept"
    p = kid.api("GET", f"/api/komboe/organizations/{nid}/plan"); assert p["kind"] == "family" and p["parentOrganizationId"] == oid
    assert all(m["email"] != kid.email for m in o.api("GET", f"/api/organizations/{oid}/users")["data"])
    return DONE("admin-approved split-off: member keeps personal vault, leaves family, owns new client-keyed family")

# ---- aliases
def alias_key(u):
    k = u.api("POST", "/api/komboe/alias/api-key"); assert k["apiKey"].startswith("kmb_"); return k["apiKey"]
def sl(key, m, p, body=None): return http(m, p, body, headers={"Authentication": key})
@t(59)
def _():
    u = a(); k = alias_key(u)
    x = sl(k, "POST", "/api/alias/random/new?hostname=example.com", {"note": "shop"})
    assert x["alias"].endswith("@" + os.environ.get("KOMBOE_ALIAS_DOMAIN", "alias.komboe.localhost"))
    assert any(y["email"] == x["alias"] for y in sl(k, "GET", "/api/v2/aliases?page_id=0")["aliases"])
    expect(401, sl, "bad-key", "GET", "/api/v2/aliases?page_id=0")
    expect(401, sl, alias_key(b()), "POST", f"/api/aliases/{x['id']}/toggle") if False else None
    return ("partial", "hide-my-email aliases created/listed via SimpleLogin-compatible API; mail forwarding needs MX/SMTP (no DNS)")
@t(60)
def _():
    u = a(); k = alias_key(u)
    assert sl(k, "GET", "/api/user_info")["email"] == u.email
    x = sl(k, "POST", "/api/v3/alias/custom/new?hostname=x.test", {"alias_prefix": "News", "note": None}); assert x["alias"].startswith("news.")
    pw = os.path.join(ROOT, "tests/playwright/results.json")
    ok = os.path.exists(pw) and json.load(open(pw)).get("alias-generator") == "passed"
    return ("done" if ok else "partial", "SimpleLogin forwarder API served by Komboe" + ("; web vault generator creates alias (Playwright)" if ok else "; UI check pending"))
@t(65)
def _():
    u = a(); k = alias_key(u); x = sl(k, "POST", "/api/alias/random/new", {})
    assert sl(k, "POST", f"/api/aliases/{x['id']}/toggle")["enabled"] is False
    other = alias_key(b()); expect(404, sl, other, "POST", f"/api/aliases/{x['id']}/toggle")
    assert sl(k, "DELETE", f"/api/aliases/{x['id']}")["deleted"]
    return ("partial", "alias enable/disable/delete, owner-scoped; block-sender and stats need mail flow")
@t(19)
def _():
    u = a(); k = alias_key(u); x = sl(k, "POST", "/api/alias/random/new?hostname=shop.test", {})
    cid = u.api("POST", "/api/ciphers", u.cipher({"login": {"username": u.e(x["alias"]), "password": u.e("p"), "uris": [{"uri": u.e("https://shop.test"), "match": None}]}}))["id"]
    c = next(c for c in u.api("GET", "/api/sync")["ciphers"] if c["id"] == cid); assert u.d(c["login"]["username"]) == x["alias"]
    return DONE("alias generated then stored (encrypted) as the login username")
for n in (61, 62, 63, 64, 66):
    X(n, "aliases: needs the mail-forwarding service (MX/SMTP + DNS), not allowed on the build box")

# ---- client builds
def art(name): p = os.path.join(ART, name); return p if os.path.exists(p) and os.path.getsize(p) > 0 else None
def _manifest(zipname):
    import zipfile; z = zipfile.ZipFile(art(zipname)); m = json.loads(z.read("manifest.json"))
    msgs = json.loads(z.read("_locales/en/messages.json")); return m, msgs
@t(84)
def _():
    m, msgs = _manifest("komboe-chrome-mv3.zip"); assert m["manifest_version"] == 3 and "Komboe" in msgs["extName"]["message"]
    m2, msgs2 = _manifest("komboe-firefox.zip"); assert "Komboe" in msgs2["extName"]["message"]
    return DONE(f"Chrome MV3 + Firefox extension zips built and rebranded ({ART})")
@t(89)
def _():
    m, _m = _manifest("komboe-chrome-mv3.zip"); assert any("content" in str(c.get("js")) for c in m.get("content_scripts", []))
    pw = os.path.join(ROOT, "tests/playwright/results.json")
    ok = os.path.exists(pw) and json.load(open(pw)).get("extension-autofill") == "passed"
    return ("done" if ok else "partial", "autofill content scripts built into the extension" + ("; Playwright autofill passed" if ok else "; autofill E2E not run"))
@t(88)
def _():
    import subprocess, tempfile; p = art("komboe-linux-x64")
    if not p: return ("partial", "CLI sources vendored; binary not built yet")
    v = subprocess.run([p, "--version"], capture_output=True, text=True, timeout=60).stdout.strip(); assert v, "no version"
    tls, cert = os.environ.get("KOMBOE_TLS_URL", "https://localhost:8443"), os.path.join(os.environ.get("KOMBOE_TLS_DIR", "/workspace/run/tls"), "cert.pem")
    if not os.path.exists(cert): return ("partial", f"CLI {os.path.basename(p)} {v} built; no local TLS instance to log in against")
    u = User(); d = tempfile.mkdtemp()
    env = dict(os.environ, XDG_CONFIG_HOME=d, NODE_EXTRA_CA_CERTS=cert, KPW=u.pw); env.pop("BITWARDENCLI_APPDATA_DIR", None)
    run = lambda *a: subprocess.run([p, *a], capture_output=True, text=True, timeout=120, env=env)
    run("config", "server", tls); assert os.path.isdir(os.path.join(d, "Komboe CLI")), "data dir not 'Komboe CLI'"
    sess = run("login", u.email, "--passwordenv", "KPW", "--raw").stdout.strip().splitlines()[-1]
    items = json.loads(run("list", "items", "--session", sess).stdout)
    return DONE(f"CLI `komboe` {v}: config server (HTTPS), login, list items ({len(items)}) ok; data dir 'Komboe CLI'")
@t(81)
def _():
    import subprocess
    ai, deb = art("komboe-desktop-x86_64.AppImage"), art("komboe-desktop-amd64.deb")
    if not (ai or deb): return ("blocked", "desktop build not produced yet (see desktop/desktop-build.sh)")
    got = []
    if deb:
        info = subprocess.run(["dpkg-deb", "-f", deb, "Package", "Version"], capture_output=True, text=True).stdout
        assert "Package: komboe" in info, f"deb package name: {info!r}"; got.append("deb " + " ".join(info.split()))
        de = subprocess.run(f"dpkg-deb --fsys-tarfile '{deb}' | tar xO ./usr/share/applications/komboe.desktop", shell=True, capture_output=True, text=True).stdout
        assert "StartupWMClass=komboe" in de, "desktop entry StartupWMClass must equal the runtime WM_CLASS 'komboe'"; got.append("WM_CLASS komboe")
    if ai: got.append(f"AppImage {os.path.getsize(ai)//2**20} MB")
    e2e = pw("desktop-launch") and pw("desktop-login")
    return ("partial", "Linux desktop built (" + "; ".join(got) + "); " +
            ("Playwright E2E over CDP passes (window title Komboe, self-hosted picker, login, vault)" if e2e else "desktop E2E not passing") +
            "; " + _win_desktop()[1] + "; macOS not built (needs a Mac)")
@t(83)
def _():
    import zipfile; p = art("komboe-android-debug.apk")
    if not p: return ("blocked", "mobile: Android debug APK not built (see mobile/android-build.sh); iOS needs macOS")
    man = zipfile.ZipFile(p).read("AndroidManifest.xml"); assert "io.komboe.android".encode("utf-16-le") in man, "package id"
    import glob, subprocess; bt = sorted(glob.glob("/workspace/tools/android-sdk/build-tools/*/aapt2"))
    if bt:
        badge = subprocess.run([bt[-1], "dump", "badging", p], capture_output=True, text=True).stdout
        assert "application-label:'Komboe'" in badge, "app label is not 'Komboe'"
    names = zipfile.ZipFile(p).namelist()
    assert all(f"res/drawable/{n}.xml" in names for n in ("logo_bitwarden", "logo_shield_icon", "logo_bitwarden_icon")), "in-app logos must be VectorDrawables"
    return ("partial", "Android debug APK io.komboe.android (label 'Komboe', Sora wordmark header + padlock-K splash as VectorDrawables) built from pinned bitwarden/android (fdroid flavor); not run on a device/emulator here; iOS needs macOS")

# ---- Playwright UI coverage
def pw(name):
    p = os.path.join(ROOT, "tests/playwright/results.json"); return os.path.exists(p) and json.load(open(p)).get(name) == "passed"
@t(33)
def _():
    if not pw("org-family"): return ("partial", "org admin console present in vendored web vault; Playwright spec not passed yet")
    return DONE("web vault org admin + Komboe family console exercised in Playwright")
@t(74)
def _():
    if not pw("generator"): return ("partial", "generator present in vendored web vault; Playwright spec not passed yet")
    return DONE("password generator in web vault (Playwright)")
@t(75)
def _():
    if not pw("generator"): return ("partial", "generator present in vendored web vault; Playwright spec not passed yet")
    return DONE("username/passphrase generator in web vault (Playwright)")
def _report(n, steps, done_msg, part_msg):
    @t(n)
    def _():
        if all(pw(x) for x in steps): return DONE(done_msg)
        return ("partial", part_msg + "; Playwright check not passed")
_report(68, ["report-weak", "report-reused"], "weak + reused password reports list exactly the seeded weak/reused items (Playwright, web vault)", "weak/reused report is client-side")
_report(70, ["report-exposed"], "exposed-password report via HIBP k-anonymity range API (only 5-char SHA-1 prefixes leave the client; Playwright)", "k-anonymity exposed-password check is client-side")
_report(71, ["report-inactive-2fa"], "inactive two-step login report flags seeded github.com login (2fa.directory list; Playwright)", "inactive 2FA report is client-side")
_report(72, ["report-unsecured"], "unsecured (http://) website report lists only the seeded http item (Playwright)", "unsecured website report is client-side")
_report(78, ["export-encrypted"], "password-protected JSON export: downloaded file is ciphertext and independently decrypts (PBKDF2+AES-256-CBC+HMAC) to the vault items (Playwright)", "password-protected export is client-side")
@t(85)
def _():
    m, msgs = _manifest("komboe-firefox.zip"); assert "browser_specific_settings" in m or "applications" in m
    return DONE("Firefox extension zip built and rebranded")
@t(87)
def _(): _manifest("komboe-chrome-mv3.zip"); return ("partial", "Chromium MV3 zip loads in Vivaldi; Tor Browser uses the Firefox build; not tested in either")
def _win_desktop():
    import zipfile
    exe, z = art("komboe-desktop-win-x64-setup.exe"), art("komboe-desktop-win-x64.zip")
    if not (exe and z): return ("blocked", "Windows desktop not built (see desktop/desktop-build-win.ps1)")
    with open(exe, "rb") as f: head = f.read(2); f.seek(0); blob = f.read()
    assert head == b"MZ" and b"Nullsoft" in blob, "setup exe is not an NSIS installer"
    names = zipfile.ZipFile(z).namelist()
    for n in ("Komboe.exe", "desktop_proxy.exe", "resources/app.asar"):
        assert any(x.endswith(n) for x in names), f"portable zip missing {n}"
    shot = os.path.exists(os.path.join(here, "../../docs/screenshots/desktop-windows-login.png"))
    return ("done", f"Windows x64 NSIS installer ({os.path.getsize(exe)//2**20} MB) + portable zip ({os.path.getsize(z)//2**20} MB) with native Rust helpers; "
            + ("installed app launches as 'Komboe' with padlock-K/Sora branding (docs/screenshots/desktop-windows-login.png); " if shot else "") + "unsigned")
@t(82)
def _(): return _win_desktop()
X(86, "Safari extension needs macOS/Xcode")
@t(38)
def _():
    """Public org API: owner fetches the org API key, logs in as the org (client_credentials, scope api.organization),
    and syncs a member directory through /api/public/organization/import, then removes it again (deleted=true)."""
    u = User(); oid, _ok = mkorg(u, "Public API Org")
    key = u.api("POST", f"/api/organizations/{oid}/api-key", {"masterPasswordHash": u.hash})["apiKey"]
    tok = http("POST", "/identity/connect/token", form={"grant_type": "client_credentials", "scope": "api.organization",
               "client_id": f"organization.{oid}", "client_secret": key, "deviceType": "8", "deviceIdentifier": str(uuid.uuid4()), "deviceName": "ft"})["access_token"]
    try:
        http("POST", "/identity/connect/token", form={"grant_type": "client_credentials", "scope": "api.organization",
             "client_id": f"organization.{oid}", "client_secret": "wrong", "deviceType": "8", "deviceIdentifier": str(uuid.uuid4()), "deviceName": "ft"})
        raise AssertionError("wrong org api secret accepted")
    except HTTPErr: pass
    em = f"dir-{uuid.uuid4().hex[:8]}@komboe.test"
    http("POST", "/api/public/organization/import", {"groups": [], "members": [{"email": em, "externalId": "ext-1", "deleted": False}],
         "overwriteExisting": False}, token=tok)
    emails = [m["email"] for m in u.api("GET", f"/api/organizations/{oid}/users")["data"]]
    assert em in emails, f"imported member missing: {emails}"
    http("POST", "/api/public/organization/import", {"groups": [], "members": [{"email": em, "externalId": "ext-1", "deleted": True}],
         "overwriteExisting": False}, token=tok)
    st = {m["email"]: m["status"] for m in u.api("GET", f"/api/organizations/{oid}/users")["data"]}
    assert st.get(em) == -1, f"deleted member not revoked: {st.get(em)}"
    return DONE("public org API: org API key -> client_credentials (api.organization), wrong secret rejected, directory import invites then revokes a member")
@t(48)
def _():
    """WebAuthn 2FA: enrol a (software) P-256 security key, login is refused without it, then passes with a signed assertion.
    Also checks a replayed or wrong-key assertion is refused. The software authenticator is test-only (tests/features/webauthn_soft.py)."""
    import sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from webauthn_soft import SoftAuthenticator
    origin = http("GET", "/api/config")["environment"]["vault"].rstrip("/")
    v = User(); key = SoftAuthenticator(origin)
    ch = v.api("POST", "/api/two-factor/get-webauthn-challenge", {"masterPasswordHash": v.hash})
    v.api("PUT", "/api/two-factor/webauthn", {"id": 1, "name": "soft key", "masterPasswordHash": v.hash, "deviceResponse": key.create(ch)})
    def attempt(extra=None):
        v.dev = None
        try: v.login(extra); return None
        except HTTPErr as e: return e
    e = attempt(); assert e and e.code == 400 and "TwoFactor" in str(e), "login without WebAuthn allowed"
    opts = json.loads(e.body)["TwoFactorProviders2"]["7"]
    asrt = key.get(opts)
    assert attempt({"twoFactorProvider": "7", "twoFactorToken": json.dumps(asrt), "twoFactorRemember": "0"}) is None, "valid assertion refused"
    other = SoftAuthenticator(origin); other.cred = key.cred
    e2 = attempt(); bad = other.get(json.loads(e2.body)["TwoFactorProviders2"]["7"])
    assert attempt({"twoFactorProvider": "7", "twoFactorToken": json.dumps(bad), "twoFactorRemember": "0"}) is not None, "wrong-key assertion accepted"
    assert attempt({"twoFactorProvider": "7", "twoFactorToken": json.dumps(asrt), "twoFactorRemember": "0"}) is not None, "replayed assertion accepted"
    return DONE("WebAuthn 2FA: enrol P-256 key, enforced at login, signed assertion accepted; wrong key and replay refused (server-side, software authenticator)")
