"""Generates static pages (shared header/footer). Run: python3 build.py"""
import os, json, re, html as H, datetime as _d
NAV = [("index.html", "Home"), ("features.html", "Features"), ("security.html", "Security"), ("pricing.html", "Pricing"), ("downloads.html", "Downloads"), ("developers.html", "Developers")]
BASE = "https://komboe.com"
STAGING = os.environ.get("KOMBOE_ENV", "staging") != "production"
LOCALES = ["en"]
CSP = (
    "default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; style-src 'self'; "
    "img-src 'self'; font-src 'self'; connect-src 'self'; form-action 'self'; "
    "base-uri 'self'; object-src 'none'"
)
HERE = os.path.dirname(os.path.abspath(__file__))

def ld_script(pre, name):
    return f'<script type="application/ld+json" src="{pre}assets/ld/{name}.json"></script>'

def page(fn, title, body, pre="", desc="", crumbs=None, extra=()):
    nav = "".join(f'<a href="{pre}{h}"{" class=on aria-current=page" if h == fn else ""}>{t}</a>' for h, t in NAV)
    path = "/" if fn == "index.html" else "/" + fn
    url = BASE + path
    desc = desc or "Komboe is an open-source, zero-knowledge password manager."
    full = f"{title} · Komboe" if fn != "index.html" else f"Komboe — {title}"
    robots = '<meta name="robots" content="noindex,nofollow">' if STAGING or fn in ("privacy.html", "terms.html", "404.html", "vault/index.html", "vault/signup/index.html") else '<meta name="robots" content="index,follow">'
    alt = "".join(f'<link rel="alternate" hreflang="{l}" href="{BASE}{"" if l == "en" else "/" + l}{path}">' for l in LOCALES) + f'<link rel="alternate" hreflang="x-default" href="{url}">'
    stem = fn.replace("/", "-").replace(".html", "")
    lds = []
    for i, obj in enumerate(list(extra)):
        name = f"{stem}-{i}"
        os.makedirs(os.path.join(HERE, "assets/ld"), exist_ok=True)
        open(os.path.join(HERE, "assets", "ld", name + ".json"), "w").write(json.dumps(obj, ensure_ascii=False))
        lds.append(ld_script(pre, name))
    login = f'<a href="{pre}index.html#signin">Log in</a>'
    return EXT(f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{full}</title><meta name="description" content="{H.escape(desc)}">{robots}<link rel="canonical" href="{url}">{alt}
<meta property="og:type" content="website"><meta property="og:site_name" content="Komboe"><meta property="og:title" content="{H.escape(full)}"><meta property="og:description" content="{H.escape(desc)}"><meta property="og:url" content="{url}"><meta property="og:image" content="{BASE}/assets/img/og.png"><meta property="og:image:width" content="1200"><meta property="og:image:height" content="630"><meta property="og:image:alt" content="Komboe padlock-K logo"><meta property="og:locale" content="en_US">
<meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="{H.escape(full)}"><meta name="twitter:description" content="{H.escape(desc)}"><meta name="twitter:image" content="{BASE}/assets/img/og.png">
<meta http-equiv="Content-Security-Policy" content="{CSP}">
<link rel="icon" href="{pre}assets/img/favicon.ico" sizes="any"><link rel="icon" type="image/png" sizes="32x32" href="{pre}assets/img/favicon-32.png"><link rel="apple-touch-icon" href="{pre}assets/img/apple-touch-icon-180.png"><link rel="manifest" href="{pre}site.webmanifest"><meta name="theme-color" content="#09080f">
<link rel="preload" href="{pre}assets/fonts/Sora-Variable.woff2" as="font" type="font/woff2" crossorigin><link rel="stylesheet" href="{pre}assets/style.css">{"".join(lds)}</head><body>
<a class="skip" href="#main">Skip to content</a><header><div class="wrap nav"><a class="brand" href="{pre}index.html"><img src="{pre}assets/img/logo-96.webp" width="34" height="34" alt="Komboe logo">Komboe</a><button id="menu" type="button" aria-label="Menu">Menu</button>
<nav class="links" aria-label="Main">{nav}{login}<a class="btn p" href="{pre}signup.html">Get started</a></nav></div></header>
<main id="main">{body}</main>
<aside id="assistant" class="card glass assistant wrap" aria-label="Komboe assistant"><h2>Komboe assistant</h2><p class="fine">Asks your Komboe agent after you sign in. It can explain a feature, suggest next steps, or generate a password. It never reads vault items.</p>
<form id="assistant-form"><label class="field">Feature <input id="assistant-q" name="feature" maxlength="80" placeholder="passkeys"></label><div class="row"><button class="btn p" type="submit">Explain</button><button class="btn" id="assistant-password" type="button">Generate a password</button><button class="btn" id="assistant-steps" type="button">Suggest next steps</button></div></form>
<pre id="assistant-out" class="out"></pre></aside>
<footer><div class="wrap"><div><b>Komboe</b> · Zero-knowledge password manager</div><nav aria-label="Footer"><a href="{pre}features.html">Features</a> · <a href="{pre}security.html">Security</a> · <a href="{pre}pricing.html">Pricing</a> · <a href="{pre}downloads.html">Downloads</a> · <a href="{pre}developers.html">Developers</a> · <a href="{pre}features.html#open-source">Source</a> · <a href="{pre}privacy.html">Privacy</a> · <a href="{pre}terms.html">Terms</a></nav><div>{"© 2026 GODESK IO LLC" if fn in ("privacy.html", "terms.html") else "© 2026 Komboe"}</div></div></footer>
<script src="{pre}assets/vendor/argon2.js" defer></script><script src="{pre}assets/app.js" defer></script>
<script src="{pre}assets/auth.js" type="module"></script><script src="{pre}assets/agent.js" type="module"></script><script src="{pre}assets/vault.js" type="module"></script>
</body></html>""")

def EXT(h):
    def f(m):
        t = m.group(0)
        if "rel=" in t:
            t = re.sub(r'rel="[^"]*"', 'rel="noopener noreferrer"', t)
        else:
            t = t[:-1] + ' rel="noopener noreferrer"' + ">"
        if "target=" not in t:
            t = t[:-1] + ' target="_blank">'
        return t
    return re.sub(r'<a [^>]*href="https?://[^"]*"[^>]*>', f, h)

def also(name, url):
    return f'<p class="also">Also offered by <a class="src" href="{url}">{H.escape(name)}</a></p>'

def cards(items):
    parts = []
    for it in items:
        icon, title, desc = it[:3]
        extra = it[3] if len(it) > 3 else ""
        parts.append(f'<div class="card glass"><div class="ic" aria-hidden="true">{icon}</div><h3>{title}</h3><p>{desc}</p>{extra}</div>')
    return '<div class="grid">' + "".join(parts) + "</div>"

FEAT = [
    ("🔐", "Encrypted vault", "Passwords, notes, cards and identities are encrypted on your device before anything syncs. The server stores ciphertext only.", also("Bitwarden", "https://github.com/bitwarden/clients")),
    ("🧩", "Browser extension", "Autofill and save logins from the page you are on, with the same Komboe account as the vault.", also("Bitwarden", "https://github.com/bitwarden/clients")),
    ("🤖", "Android", "A native autofill service and biometric unlock on your phone, using the same account as every other Komboe app.", also("Bitwarden", "https://github.com/bitwarden/android")),
    ("🖥️", "Desktop", "Apps for the major desktop systems, with a tray for quick access and the same vault you use on the web.", also("KeePassXC", "https://github.com/keepassxreboot/keepassxc")),
    ("🌐", "Web vault", "Open the vault in a modern browser. Decryption still happens on the device after you sign in.", also("Vaultwarden", "https://github.com/dani-garcia/vaultwarden")),
    ("🪪", "Passkeys", "Create, store and sign in with passkeys next to your passwords. The private key never leaves the device.", also("Bitwarden", "https://github.com/bitwarden/clients")),
    ("🤝", "Secure sharing", "Share an item or a collection with family and teammates. The server never sees the shared secret.", also("Passbolt", "https://github.com/passbolt/passbolt_api")),
    ("✨", "AI agent", "A signed-in assistant can explain a feature, suggest next steps, or generate a password. It cannot read vault items.", also("the Komboe repository", "https://github.com/GoDeskio/Komboe")),
]
SIGNIN = '''<div class="card glass signin" id="signin"><h2>Sign in</h2>
<form id="login-form" method="post" action="">
<label class="field">Email or login name <input id="email" name="email" type="text" autocomplete="username" required></label>
<label class="field">Master password <span class="pw"><input id="master-password" name="password" type="password" autocomplete="current-password" required><button class="btn eye" type="button" data-eye="master-password" aria-pressed="false">Show</button></span></label>
<p id="login-error" class="error" role="alert" hidden></p>
<div id="twofactor" hidden><label class="field"><span id="twofactor-label">Authenticator code</span><input id="twofactor-code" name="code" inputmode="numeric" autocomplete="one-time-code"></label></div>
<button class="btn p full" id="login-submit" type="submit">Log in</button>
<p class="sso"><a href="signup.html">Create account</a></p>
</form>
<a class="btn p full" id="open-dashboard" href="vault/" hidden>Open dashboard</a>
<noscript><p class="fine">Sign-in runs in the browser so your master password is hashed before it is sent.</p></noscript>
</div>'''
home = f'''<section class="hero"><div class="wrap hero-grid"><div class="hero-copy"><img class="logo" src="assets/img/logo-240.webp" width="96" height="96" alt="Komboe padlock-K logo" fetchpriority="high">
<h1>Your secrets.<br><span class="grad">Only yours.</span></h1><p>Komboe is a zero-knowledge password manager. Your master password stays on this device, and there is no backdoor and no admin password reset.</p>
<div class="cta"><a class="btn" href="downloads.html">Download Komboe</a></div></div>{SIGNIN}</div></section>
<section><div class="wrap"><h2>Everything in one vault</h2><p class="lead">One encrypted home for every login, passkey and secret, on every device you use.</p>{cards(FEAT[:4])}<p class="sso"><a href="features.html">See all features</a></p></div></section>
<section class="band"><div class="wrap split"><div><h2>Zero-knowledge by design</h2><p class="lead">Your master password never leaves your device. Vault contents are encrypted before upload. Account metadata is described in the <a href="privacy.html">Privacy Policy</a>.</p><a class="btn" href="security.html">How Komboe protects you</a></div>
{cards([("🚫", "No backdoor", "There is no master key and no way for Komboe to decrypt your data."), ("🔁", "No admin reset", "Admins cannot reset your master password. Keep your recovery kit safe.")])}</div></section>
<section><div class="wrap"><h2>One Komboe account</h2><p class="lead">One Komboe account syncs the web vault, browser extensions, phone, desktop, CLI and the assistant. Your master password unlocks it and never leaves your device.</p><a class="btn p" href="signup.html">Create account</a></div></section>'''
SRC = {"PP": ("Proton Pass", "https://proton.me/pass", None), "BW": ("Bitwarden", "https://github.com/bitwarden/clients", "GPL-3.0"), "VW": ("Vaultwarden", "https://github.com/dani-garcia/vaultwarden", "AGPL-3.0"), "KP": ("KeePassXC", "https://github.com/keepassxreboot/keepassxc", None), "PB": ("Passbolt", "https://github.com/passbolt/passbolt_api", None), "PD": ("Padloc", "https://github.com/padloc/padloc", None), "PS": ("Psono", "https://gitlab.com/psono/psono-server", None), "SL": ("SimpleLogin", "https://github.com/simple-login/app", "AGPL-3.0")}
rows = []
excl = []
for line in open(os.path.join(HERE, "../../docs/FEATURES.md")):
    m = re.match(r"\|\s*(\d+)\s*\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|", line)
    if m:
        n, cat, f, src, st, note = [x.strip() for x in m.groups()]
        if f.startswith(("Proton-style dashboard UI", "Third-party audits published")):
            continue
        (excl if st == "Excluded" else rows).append((int(n), cat, f, src, st, note))

def srclinks(src, note, cat, f):
    if "GoDesk-original" in src:
        return '<span class="src orig">Komboe-original</span>'
    out = []
    for k in [x.strip() for x in src.split(",")]:
        name, url, lic = SRC[k]
        if k == "BW" and "Mobile" in f:
            url = "https://github.com/bitwarden/android"
        out.append(f'<a class="src" href="{url}">{name}</a>')
    return "Also offered by " + " ".join(out)

cats = []
for r in rows:
    if r[1] not in cats:
        cats.append(r[1])

def badge(st):
    if st == "Review":
        return ' <span class="st">planned with constraints</span>'
    if "reimplement" in st:
        return ' <span class="st">clean-room reimplementation</span>'
    return ""

full = "".join('<h3 class="cat">' + c + '</h3><ul class="flist">' + "".join('<li class="card glass"><span class="fname">' + H.escape(f) + "</span>" + badge(st) + "<p>" + H.escape(note) + '</p><span class="srcs">' + srclinks(src, note, cc, f) + "</span></li>" for n, cc, f, src, st, note in rows if cc == c) + "</ul>" for c in cats)
exl = "".join('<li class="card glass"><span class="fname">' + H.escape(f) + '</span><p>' + H.escape(note) + "</p></li>" for n, c, f, src, st, note in excl)
features = ('<section class="hero"><div class="wrap"><h1>Features</h1><p>Everything you need to keep credentials safe and close at hand: ' + str(len(rows)) + ' features, each with the other products that offer the same idea.</p><div class="note">Komboe is pre-alpha. This is the planned feature scope.</div></div></section>'
 + '<section><div class="wrap"><h2>Highlights</h2>' + cards(FEAT) + '</div></section>'
 + '<section class="band" id="open-source"><div class="wrap"><h2>Every feature</h2><p class="lead">Names inside these cards point at the projects that offer the same feature. Komboe itself is independent of those projects.</p>'
 + full + '<h3 class="cat">Deliberately not included</h3><ul class="flist">' + exl + "</ul></div></section>")
SH_LONG = "A self-hosted Komboe server does not contact Komboe. Outside services stay off unless you turn them on. Desktop and CLI update checks stay off until you point them at a feed you host. A breach check runs only when you ask for it. Password checks send only a k-anonymity hash prefix, never the password. The data breach report sends your email address to your Komboe server, which forwards it only if the operator has configured a breach-check key. The web vault uses the server it was loaded from. Until you save a server URL, some apps still have a cloud default compiled in. Set your server URL when you first sign in."
SH_SHORT = "Your self-hosted server never contacts Komboe, and outside services stay off unless you turn them on or run a check. Set your server URL in the apps when you first sign in."
SWITCH = "The switch list is in docs/RUNNING.md in the Komboe source."
security = f'''<section class="hero"><div class="wrap"><h1>Security and <span class="grad">zero-knowledge</span></h1><p>Vault contents are encrypted on your device before upload. Account metadata is described in the <a href="privacy.html">Privacy Policy</a>.</p></div></section>
<section><div class="wrap"><h2>How Komboe protects your vault</h2>{cards([("🧮", "On-device encryption", "Every vault item is encrypted on your device before it is stored or synced."), ("🗝️", "Master password stays local", "Your master password never leaves your device. Keys are uploaded only in encrypted form."), ("☁️", "Encrypted before upload", "A copy of the server alone does not reveal vault contents."), ("🚫", "No backdoor", "No escrow key, no hidden recovery path, no exceptions."), ("🔁", "No admin password reset", "Neither Komboe nor an organization admin can reset your master password."), ("🔍", "Open source", "The Komboe source is public so anyone can read how the vault is protected.")])}</div></section>
<section class="band"><div class="wrap"><h2>One account, every device</h2><p class="lead">You sign in with your email and master password, and optionally a passkey and two-step login. The password is used on the device to derive the keys that decrypt the vault.</p></div></section>
<section id="self-hosting"><div class="wrap"><h2>Self-hosting</h2><p class="lead">{SH_LONG} {SWITCH}</p></div></section>'''
tiers = [("Free", "$0", "Personal starter", ["Unlimited passwords", "Passkeys", "Two-step login"]), ("Plus", "Coming soon", "", ["All devices", "Secure sharing", "Vault health report"]), ("Family", "Coming soon", "", ["Shared collections", "Up to 6 members", "Everything in Plus"]), ("Business", "Coming soon", "", ["Organization admin", "Assistant for teams", "Activity reports"])]
pricing = '<section class="hero"><div class="wrap"><h1>Pricing</h1><p>Simple plans for individuals, families and teams.</p><p class="sso">Paid plan prices will be announced at launch.</p></div></section><section><div class="wrap"><h2>Plans</h2><div class="grid">' + "".join(f'<div class="card glass{" hl" if n == "Plus" else ""}"><h3>{n}</h3><div class="price">{p} <small>{s}</small></div><ul>{"".join(f"<li>{x}</li>" for x in L)}</ul><a class="btn{" p" if n == "Plus" else ""} full" href="signup.html">Choose {n}</a></div>' for n, p, s, L in tiers) + "</div></div></section>"
PH = '<span class="meta">Version and SHA-256 checksum will be published with the first release.</span>'

import html as _html
import json as _json
from pathlib import Path as _Path
_MANIFEST = _json.loads((_Path(__file__).resolve().parents[2] / "distribution" / "komboe-downloads.json").read_text(encoding="utf-8"))
_OS = {"desktop-windows": "windows", "desktop-macos": "macos", "desktop-linux-deb": "linux", "desktop-linux-appimage": "linux", "android": "android", "ios": "ios", "extension-chromium-mv3": "ext-chrome ext-edge ext-brave", "extension-firefox": "ext-firefox"}

def _manifest_card(asset):
    name = _html.escape(asset["name"])
    platforms = _html.escape(", ".join(asset["platforms"]))
    os_attr = _html.escape(_OS.get(asset["id"], asset["id"]))
    url = asset.get("url") or ""
    if asset.get("status") == "published" and url.startswith(("https://", "http://")):
        body = f'<p><strong>Unsigned testing build</strong></p><p><a class="btn p" href="{_html.escape(url, quote=True)}">Download {_html.escape(asset.get("filename") or "file")}</a></p>'
        if asset.get("sha256"):
            body += f'<p class="fine">sha256 {_html.escape(asset["sha256"])}</p>'
    else:
        body = f'<p><strong>Not available.</strong> {_html.escape(asset.get("reason") or "")}</p>'
    docs = f'<p><a href="{_html.escape(asset["docsUrl"], quote=True)}">Instructions</a></p>'
    return f'<article class="card glass" data-os="{os_attr}" data-testid="marketing-download-{_html.escape(asset["id"], quote=True)}"><h3>{name}</h3><p>{platforms}</p>{body}{docs}</article>'

_manifest_cards = "".join(_manifest_card(asset) for asset in _MANIFEST["assets"])
_empty = "" if any(asset.get("status") == "published" and str(asset.get("url") or "").startswith(("https://", "http://")) for asset in _MANIFEST["assets"]) else '<p data-testid="downloads-manifest-empty">No installer file is in this manifest. There is no download link and no QR code.</p>'
downloads = (
    '<section class="hero"><div class="wrap"><h1>Download Komboe</h1>'
    '<p>Installers come from the same release manifest as the signed-in vault. This browser looks like: <b id="detected">this device</b></p>'
    '<p class="sso">A link appears only when that manifest has a real file. Store listings for other password managers are not Komboe.</p></div></section>'
    '<section class="tight" id="release-manifest"><div class="wrap"><h2>Release manifest</h2>'
    + _empty
    + f'<div class="grid">{_manifest_cards}</div></div></section>'
    + '<section class="tight"><div class="wrap"><h2>Web vault</h2><div class="grid">'
    + '<div class="card glass dl" data-os="web"><div class="ic">🌐</div><h3>Web vault</h3><p>No install. Sign in on the home page.</p><a class="btn p full" href="index.html#signin">Sign in</a></div>'
    + '</div><p class="lead">Check the SHA-256 checksum of a download before installing. '
    + SH_SHORT + " " + SWITCH + "</p></div></section>"
)
def auth(mode):
    sg = mode == "signup"
    return f"""<section class="hero"><div class="wrap"><div class="card glass auth"><img src="assets/img/logo-96.webp" alt="Komboe logo" width="52" height="52"><h1>{"Create your Komboe account" if sg else "Log in to Komboe"}</h1>
<p>{"One Komboe account syncs the web vault, browser extensions, phone, desktop, command line and the assistant." if sg else "Use the sign-in form on the home page. It is the same account as the web vault."}</p>
<ul class="steps"><li>{"Choose your email and a strong master password" if sg else "Enter your email and master password"}</li><li>{"You can add a passkey and two-step login later" if sg else "If two-step login is on, the form asks for the code"}</li><li>Your vault is decrypted on your device only</li></ul>
<a class="btn p full" href="{"signup.html" if sg else "index.html#signin"}">{"Create account" if sg else "Sign in on the home page"}</a>
<p class="sso">Your master password is hashed in the browser. Komboe stores the hash, not the password, and cannot reset it.</p>
<p class="sso">{'Already have an account? <a href="index.html#signin">Log in</a>' if sg else 'New here? <a href="signup.html">Create account</a>'}</p></div></div></section>"""
dev = '<section class="hero"><div class="wrap"><h1>Developers</h1><p>Komboe is open source. Self-host it, and read how the vault is protected from the features page.</p><div class="cta"><a class="btn p" href="features.html#open-source">Source</a></div></div></section><section><div class="wrap"><h2>Resources</h2>' + cards([
    ("🗄️", "Self-host", "Run your own Komboe server from the container image. Local accounts are the default. Enterprise single sign-on is optional."),
    ("⌨️", "Command line", "komboe and komboe-run script the vault and pass secrets into a process with komboe://item/field references."),
    ("✨", "Assistant", "After you sign in, the assistant on this site calls the Komboe agent. It does not read vault items."),
    ("🧮", "Encryption", "Vault items are encrypted on the device before they are stored. The design is described on the security page."),
    ("🤝", "Contribute", "Read the source from the features page, create a branch, and open a pull request."),
    ("🛡️", "Report a security issue", "Email security@komboe.com. Do not open a public report for a vulnerability. Give Komboe time to fix it first."),
]) + "</div></section>"
FAQ_ITEMS = [
    ("What is a Komboe account?", "One Komboe account syncs the web vault, browser extensions, phone, desktop, command line and the assistant. You sign in with your email and master password, and you can add a passkey and two-step login."),
    ("Does Komboe ever see my master password?", "No. The home page and the web vault hash the master password on the device. Only that hash is sent, and the vault is encrypted before it syncs."),
    ("Can an admin reset my master password?", "No. There is no backdoor and no admin password reset. Keep your recovery kit safe."),
    ("Does this website ask for my password?", "Yes. The home page sign-in form uses the same flow as the web vault, including a two-step code when the account has one. The password stays in the browser and is not stored on this site."),
    ("What about self-hosting?", "Self-hosted servers use local Komboe accounts by default. Organizations can optionally add enterprise single sign-on. Vault decryption still needs each person's master password. " + SH_LONG),
]
FAQ = '<section id="accounts"><div class="wrap"><h2>Accounts and sign-in</h2><div class="grid">' + "".join(f'<div class="card glass"><h3>{q}</h3><p>{a}</p></div>' for q, a in FAQ_ITEMS) + "</div></div></section>"
home += FAQ
security += FAQ
exec(open(os.path.join(HERE, "legal_copy.py")).read())
pages = {"index.html": ("Zero-knowledge password manager", home), "features.html": ("Features", features), "security.html": ("Security", security), "pricing.html": ("Pricing", pricing), "downloads.html": ("Downloads", downloads), "developers.html": ("Developers", dev), "login.html": ("Log in", auth("login")), "signup.html": ("Sign up", auth("signup")), "privacy.html": ("Privacy", PRIV), "terms.html": ("Terms", TERMS)}
META = {
    "index.html": ("Zero-knowledge password manager", "Komboe is an open-source, zero-knowledge password manager. One account, no backdoor, no admin password reset.", None),
    "features.html": ("Features", "Every Komboe feature, with links to other products that offer the same idea.", "Features"),
    "security.html": ("Security and zero-knowledge", "How Komboe keeps your vault zero-knowledge: on-device encryption, no backdoor and no admin password reset.", "Security"),
    "pricing.html": ("Pricing", "Komboe plans for individuals, families and businesses. The free tier is available now.", "Pricing"),
    "downloads.html": ("Downloads", "Komboe downloads follow the release manifest. An installer link appears only when a build published that file.", "Downloads"),
    "developers.html": ("Developers", "Komboe developer resources: source, self-hosting, command line, the assistant and security disclosure.", "Developers"),
    "login.html": ("Log in", "Sign in to Komboe from the home page. One account for every Komboe app.", "Log in"),
    "signup.html": ("Sign up", "Create your Komboe account with your email and master password.", "Sign up"),
    "privacy.html": ("Privacy Policy (draft)", "Draft Komboe privacy policy: what data we collect, why, your rights, and how your vault stays encrypted. Pending legal review.", "Privacy"),
    "terms.html": ("Terms of Service (draft)", "Draft Komboe terms of service for the hosted password manager. Pending legal review.", "Terms"),
}
FAQ_LD = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in FAQ_ITEMS]}
ORG = {"@context": "https://schema.org", "@type": "Organization", "name": "Komboe", "url": BASE, "logo": BASE + "/assets/img/pwa-512.png", "brand": {"@type": "Brand", "name": "Komboe"}}
APP = {"@context": "https://schema.org", "@type": "SoftwareApplication", "name": "Komboe", "applicationCategory": "SecurityApplication", "operatingSystem": "Android, Windows, macOS, Linux, Web", "url": BASE + "/", "publisher": {"@type": "Organization", "name": "Komboe"}, "offers": [{"@type": "Offer", "name": "Free", "price": "0", "priceCurrency": "USD", "url": BASE + "/pricing.html"}]}
WEBSITE = {"@context": "https://schema.org", "@type": "WebSite", "name": "Komboe", "url": BASE + "/", "inLanguage": "en"}
EXTRA = {"index.html": [ORG, WEBSITE, APP, FAQ_LD], "security.html": [FAQ_LD], "pricing.html": [APP]}
os.chdir(HERE)
open("csp.txt", "w").write(CSP + "\n")
for fn, (t, b) in pages.items():
    title, desc, cr = META[fn]
    open(fn, "w").write(page(fn, title, b, "", desc, cr, EXTRA.get(fn, ())))
open("404.html", "w").write(page("404.html", "Page not found", '<section class="hero"><div class="wrap"><h1>Page not found</h1><p>That page does not exist.</p><div class="cta"><a class="btn p" href="/index.html">Home</a><a class="btn" href="/features.html">Features</a></div></div></section>', "/", "Page not found."))

def u(f):
    return BASE + ("/" if f == "index.html" else "/" + f)

open("sitemap.xml", "w").write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "".join(f"<url><loc>{u(f)}</loc></url>\n" for f in pages if f not in ("privacy.html", "terms.html")) + "</urlset>\n")
open("robots.txt", "w").write("User-agent: *\nDisallow: /\n" if STAGING else f"User-agent: *\nAllow: /\nSitemap: {BASE}/sitemap.xml\n")
DASH = '''<section class="hero"><div class="wrap"><h1>Your vault</h1><div id="dashboard" class="card glass" data-mode="vault"><p id="dash-status">Loading your vault…</p><div id="dash-body" hidden><h2 id="dash-name">Your vault</h2><p>Signed in as <b id="dash-email"></b></p><p class="fine">Items in this vault: <b id="dash-count"></b></p><p class="fine" id="device-unlock-note"></p>
<label class="field">Email code on the next sign-in after
<select id="email-interval"></select></label>
<p class="fine" id="email-interval-help">The timer starts when an email code is accepted on this device. Failed sign-ins and opening the vault do not extend it. Never turns off only this timer. An authenticator, passkey, or other required check still applies.</p>
<label class="field">Master password to confirm <input id="email-interval-password" type="password" autocomplete="current-password"></label>
<button class="btn" id="email-interval-save" type="button">Save email timing</button>
<p id="email-interval-status" role="status"></p>
<button class="btn" id="dash-logout" type="button">Sign out</button></div></div></div></section>'''
os.makedirs("vault/signup", exist_ok=True)
open("vault/index.html", "w").write(page("vault/index.html", "Your vault", DASH, "../", "Your Komboe vault."))
open("vault/signup/index.html", "w").write(page("vault/signup/index.html", "Create account", '<section class="hero"><div class="wrap"><h1>Create account</h1><p><a class="btn p" href="../../signup.html">Create account</a></p></div></section>', "../../", "Create a Komboe account."))
os.makedirs(".well-known", exist_ok=True)
open(".well-known/security.txt", "w").write("Contact: mailto:security@komboe.com\nExpires: " + (_d.datetime.now(_d.timezone.utc) + _d.timedelta(days=365)).strftime("%Y-%m-%dT00:00:00Z") + "\nPreferred-Languages: en\nCanonical: " + BASE + "/.well-known/security.txt\n")
open("llms.txt", "w").write("# Komboe\n\n> Komboe is an open-source, zero-knowledge password manager. The master password stays on the device. There is no backdoor and no admin password reset.\n\n## Pages\n" + "".join(f"- [{META[f][0]}]({u(f)}): {META[f][1]}\n" for f in pages) + "\n")
open("komboe-downloads.json", "w").write(_json.dumps(_MANIFEST, indent=2) + "\n")
print("built", len(pages), "pages")
