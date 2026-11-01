"""Generates static pages (shared header/footer). Run: python3 build.py"""
import os
NAV=[("index.html","Home"),("features.html","Features"),("security.html","Security"),("pricing.html","Pricing"),("downloads.html","Downloads"),("developers.html","Developers")]
import json,re,html as H
BASE="https://komboe.com"
STAGING=os.environ.get("KOMBOE_ENV","staging")!="production"   # staging => noindex,nofollow + robots Disallow
LOCALES=["en"]  # path-based locales ready: add e.g. "de" -> /de/<page>
def ld(o): return '<script type="application/ld+json">'+json.dumps(o,ensure_ascii=False)+'</script>'
ORG={"@context":"https://schema.org","@type":"Organization","name":"Komboe","url":BASE,"logo":BASE+"/assets/img/pwa-512.png","brand":{"@type":"Brand","name":"Komboe"},"sameAs":["https://github.com/GoDeskio/Komboe"]}
def page(fn,title,body,pre="",desc="",crumbs=None,extra=()):
    nav="".join(f'<a href="{pre}{h}"{" class=on aria-current=page" if h==fn else ""}>{t}</a>' for h,t in NAV)
    path="/" if fn=="index.html" else "/"+fn
    url=BASE+path; desc=desc or "Komboe is an open-source, zero-knowledge password manager built on Encryptoglyph encryption."
    full=f"{title} · Komboe" if fn!="index.html" else f"Komboe — {title}"
    robots='<meta name="robots" content="noindex,nofollow">' if STAGING or fn in("privacy.html","terms.html","404.html","downloads/placeholder.html","vault/index.html","vault/signup/index.html") else '<meta name="robots" content="index,follow">'
    alt="".join(f'<link rel="alternate" hreflang="{l}" href="{BASE}{"" if l=="en" else "/"+l}{path}">' for l in LOCALES)+f'<link rel="alternate" hreflang="x-default" href="{url}">'
    lds=[ORG]+list(extra)
    if crumbs: lds.append({"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[{"@type":"ListItem","position":1,"name":"Home","item":BASE+"/"},{"@type":"ListItem","position":2,"name":crumbs,"item":url}]})
    return EXT(f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{full}</title><meta name="description" content="{H.escape(desc)}">{robots}<link rel="canonical" href="{url}">{alt}
<meta property="og:type" content="website"><meta property="og:site_name" content="Komboe"><meta property="og:title" content="{H.escape(full)}"><meta property="og:description" content="{H.escape(desc)}"><meta property="og:url" content="{url}"><meta property="og:image" content="{BASE}/assets/img/og.png"><meta property="og:image:width" content="1200"><meta property="og:image:height" content="630"><meta property="og:image:alt" content="Komboe padlock-K logo"><meta property="og:locale" content="en_US">
<meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="{H.escape(full)}"><meta name="twitter:description" content="{H.escape(desc)}"><meta name="twitter:image" content="{BASE}/assets/img/og.png">
<link rel="icon" href="{pre}assets/img/favicon.ico" sizes="any"><link rel="icon" type="image/png" sizes="32x32" href="{pre}assets/img/favicon-32.png"><link rel="apple-touch-icon" href="{pre}assets/img/apple-touch-icon-180.png"><link rel="manifest" href="{pre}site.webmanifest"><meta name="theme-color" content="#0e0c18">
<link rel="preload" href="{pre}assets/fonts/Sora-Variable.woff2" as="font" type="font/woff2" crossorigin><link rel="stylesheet" href="{pre}assets/style.css">{"".join(ld(o) for o in lds)}</head><body>
<a class="skip" href="#main">Skip to content</a><header><div class="wrap nav"><a class="brand" href="{pre}index.html"><img src="{pre}assets/img/logo-96.webp" width="34" height="34" alt="Komboe logo">Komboe</a><button id="menu" aria-label="Menu">☰</button>
<nav class="links" aria-label="Main">{nav}<a href="{pre}login.html">Log in</a><a class="btn p" href="{pre}signup.html">Get started</a></nav></div></header>
<main id="main">{body}</main>
<footer><div class="wrap"><div><b>Komboe</b> · Zero-knowledge password manager</div><nav aria-label="Footer"><a href="{pre}features.html">Features</a> · <a href="{pre}security.html">Security</a> · <a href="{pre}pricing.html">Pricing</a> · <a href="{pre}downloads.html">Downloads</a> · <a href="{pre}developers.html">Developers</a> · <a href="https://github.com/GoDeskio/Komboe">Source</a> · <a href="{pre}privacy.html">Privacy</a> · <a href="{pre}terms.html">Terms</a></nav><div>{"© 2026 GODESK IO LLC" if fn in ("privacy.html","terms.html") else "© 2026 Komboe"}</div></div></footer>
<script src="{pre}assets/app.js" defer></script></body></html>""")
def EXT(h):
    def f(m):
        t=m.group(0)
        if 'rel=' in t: t=re.sub(r'rel="[^"]*"','rel="noopener noreferrer"',t)
        else: t=t[:-1]+' rel="noopener noreferrer"'+'>'
        if 'target=' not in t: t=t[:-1]+' target="_blank">'
        return t
    return re.sub(r'<a [^>]*href="https?://[^"]*"[^>]*>',f,h)
def cards(items): return '<div class="grid">'+"".join(f'<div class="card"><div class="ic" aria-hidden="true">{i}</div><h3>{t}</h3><p>{d}</p></div>' for i,t,d in items)+'</div>'
FEAT=[("🔐","Encrypted vault","Passwords, notes, cards and identities, encrypted on your device with Encryptoglyph before anything is synced."),
("🧩","Browser extension","Autofill and save logins in Chrome, Edge, Firefox, Brave and Safari."),
("🤖","Android","Native autofill service and biometric unlock on your phone."),
("🖥️","Desktop","Apps for Windows, macOS and Linux with system-tray quick access."),
("🌐","Web vault","Reach your vault from any modern browser — decryption still happens locally."),
("🪪","Passkeys","Create, store and sign in with passkeys alongside your passwords."),
("🤝","Secure sharing","Share items or collections with family and teammates, end-to-end encrypted."),
("✨","AI agent integration","Give AI agents scoped, revocable access to specific secrets through an MCP server — never your whole vault.")]
home=f'''<section class="hero"><div class="wrap"><img class="logo" src="assets/img/logo-240.webp" width="120" height="120" alt="Komboe padlock-K logo" fetchpriority="high">
<h1>Your secrets.<br><span class="grad">Only yours.</span></h1><p>Komboe is a zero-knowledge password manager. Built on Encryptoglyph encryption, with no backdoor and no admin password reset — nobody but you can open your vault.</p>
<div class="cta"><a class="btn p" href="signup.html">Create your Komboe account</a><a class="btn" href="downloads.html">Download Komboe</a></div></div></section>
<section><div class="wrap"><h2>Everything in one vault</h2><p class="lead">One encrypted home for every login, passkey and secret — on every device you use.</p>{cards(FEAT[:4])}<p style="margin-top:24px"><a href="features.html">See all features →</a></p></div></section>
<section class="band"><div class="wrap split"><div><h2>Zero-knowledge by design</h2><p class="lead">Your master password never leaves your device. Vault contents are end-to-end encrypted on your device before upload, so we can't read your vault data. We do process some account metadata, as described in the <a href="privacy.html">Privacy Policy</a>.</p><a class="btn" href="security.html">How Komboe protects you</a></div>
{cards([("🚫","No backdoor","There is no master key and no way for us to decrypt your data."),("🔁","No admin reset","Admins can't reset your master password. Keep your recovery kit safe.")])}</div></section>
<section><div class="wrap"><h2>One Komboe account</h2><p class="lead">One Komboe account syncs and protects all your devices and apps: web vault, browser extensions, Android, desktop, CLI and MCP. Your master password unlocks it and never leaves your device.</p><a class="btn p" href="signup.html">Get started</a></div></section>'''
SRC={"PP":("Proton Pass","https://proton.me/pass",None),"BW":("Bitwarden","https://github.com/bitwarden/clients","GPL-3.0"),"VW":("Vaultwarden","https://github.com/dani-garcia/vaultwarden","AGPL-3.0"),"KP":("KeePassXC","https://github.com/keepassxreboot/keepassxc",None),"PB":("Passbolt","https://github.com/passbolt/passbolt_api",None),"PD":("Padloc","https://github.com/padloc/padloc",None),"PS":("Psono","https://gitlab.com/psono/psono-server",None),"SL":("SimpleLogin","https://github.com/simple-login/app","AGPL-3.0")}
rows=[];excl=[]
for line in open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"../../docs/FEATURES.md")):
    m=re.match(r"\|\s*(\d+)\s*\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|",line)
    if m:
        n,cat,f,src,st,note=[x.strip() for x in m.groups()]
        if f.startswith(("Proton-style dashboard UI","Third-party audits published")): continue
        (excl if st=="Excluded" else rows).append((int(n),cat,f,src,st,note))
def srclinks(src,note,cat,f):
    if "GoDesk-original" in src: return '<span class="src orig">Komboe-original</span>'
    clean=any(k in note for k in ("clean-room","bitwarden_license","Bitwarden License","verify license"))
    out=[]
    for k in [x.strip() for x in src.split(",")]:
        name,url,lic=SRC[k]
        if k=="BW" and "Mobile" in f: url="https://github.com/bitwarden/android"
        if k=="SL" and cat not in ("Aliases","Items"): lic=None
        if k=="VW" and cat in ("Platform",) and "Docker" not in f: lic=None
        tag=""  # licenses live in NOTICE / THIRD-PARTY-NOTICES.md, not on chips
        out.append(f'<a class="src" href="{url}" rel="noopener">{name}</a>{tag}')
    return " ".join(out)
cats=[]
for r in rows:
    if r[1] not in cats: cats.append(r[1])
def badge(st):
    if st=="Review": return ' <span class="st">planned with constraints</span>'
    if "reimplement" in st: return ' <span class="st">clean-room reimplementation</span>'
    return ""
full="".join('<h3 class="cat">'+c+'</h3><ul class="flist">'+"".join('<li><span class="fname">'+H.escape(f)+'</span>'+badge(st)+'<span class="srcs">Inspired by / Compatible with: '+srclinks(src,note,cc,f)+'</span></li>' for n,cc,f,src,st,note in rows if cc==c)+'</ul>' for c in cats)
exl="".join('<li><span class="fname">'+H.escape(f)+'</span><span class="srcs">'+H.escape(note)+'</span></li>' for n,c,f,src,st,note in excl)
features=('<section class="hero"><div class="wrap"><h1>Features</h1><p>Everything you need to keep credentials safe and close at hand: '+str(len(rows))+' features, each credited to the projects that inspired it.</p><div class="note">Komboe is pre-alpha: this is the planned feature scope; not every feature is built or verified yet.</div></div></section>'
 '<section><div class="wrap"><h2>Highlights</h2>'+cards(FEAT)+'</div></section>'
 '<section class="band"><div class="wrap split"><div><h2>Built for AI agents, safely</h2><p class="lead">Komboe ships an MCP server so your AI agents can request only the secrets you approve. Access is scoped per agent, logged, and revocable at any time. Secrets can also be injected into processes with <code>komboe-run</code> references like <code>komboe://item/field</code>.</p></div><pre>$ komboe-run --env DB_PASS=komboe://db/password -- ./deploy.sh</pre></div></section>'
 '<section><div class="wrap"><h2>Every feature and where it came from</h2><p class="lead">Source links point to the projects that inspired each feature or that Komboe is compatible with. Where Komboe reuses a project\'s open-source code, the license is shown, per the repository <a href="https://github.com/GoDeskio/Komboe/blob/main/NOTICE">NOTICE</a> and <a href="https://github.com/GoDeskio/Komboe/blob/main/docs/UPSTREAM.md">upstream pins</a>. Komboe itself is AGPL-3.0 (server) and GPL-3.0 (clients). See the <a href="security.html">security model</a> and <a href="downloads.html">downloads</a>.</p>'
 +full+'<h3 class="cat">Deliberately not included</h3><ul class="flist">'+exl+'</ul>'
 '<p class="disc">Open-source licenses and attributions: <a href="https://github.com/GoDeskio/Komboe/blob/main/NOTICE" rel="noopener noreferrer" target="_blank">NOTICE</a> and <a href="https://github.com/GoDeskio/Komboe/blob/main/THIRD-PARTY-NOTICES.md" rel="noopener noreferrer" target="_blank">THIRD-PARTY-NOTICES.md</a></p><p class="disc">Komboe is an independent project. It is not affiliated with, endorsed by, or sponsored by Bitwarden, Vaultwarden, KeePassXC, Proton, Passbolt, Padloc, Psono or SimpleLogin. All names and trademarks belong to their respective owners.</p></div></section>')
SH_LONG="A self-hosted Komboe server does not contact Komboe. It also does not contact Bitwarden, GitHub, Cloudflare, or the websites in the vault unless you turn that on. Desktop and CLI update checks stay off until you point them at a feed you host. Have I Been Pwned is contacted only when you run a check: the exposed-passwords report, the breach-check button on a login, the CLI <code>get exposed</code> command, or the optional breach check when you set your master password. Password checks send only a k-anonymity hash prefix, never the password. The data breach report sends your email address to your Komboe server, which forwards it to Have I Been Pwned only if the server operator has configured an HIBP API key. The web vault uses the server it was loaded from. Until you save a server URL, the browser extension, desktop, CLI and Android apps default to the upstream Bitwarden cloud servers. Set your server URL when you first sign in."
SH_SHORT="Your self-hosted server never contacts Komboe, and outside services stay off unless you turn them on or run a check. Set your server URL in the apps when you first sign in."
RUNNING="https://github.com/GoDeskio/Komboe/blob/main/docs/RUNNING.md"
SWITCH=f'<a href="{RUNNING}">See the switches in docs/RUNNING.md</a>'
security=f'''<section class="hero"><div class="wrap"><h1>Security &amp; <span class="grad">zero-knowledge</span></h1><p>Vault contents are end-to-end encrypted on your device before upload, so we can't read your vault data. We do process some account metadata, as described in the <a href="privacy.html">Privacy Policy</a>.</p></div></section>
<section><div class="wrap"><h2>How Komboe protects your vault</h2>{cards([("🧮","Encryptoglyph encryption","Every vault item is encrypted on your device with Encryptoglyph before it is stored or synced."),("🗝️","Master password stays local","Your master password never leaves your device. Your encryption keys are only ever uploaded in encrypted form."),("☁️","Encrypted before upload","Vault contents are end-to-end encrypted on your device before upload, so a breach of the server alone does not reveal them. We do process some account metadata, "+'as described in the <a href="privacy.html">Privacy Policy</a>'+"."),("🚫","No backdoor","No escrow key, no hidden recovery path, no exceptions."),("🔁","No admin password reset","Neither Komboe nor an organization admin can reset your master password. Losing it and your recovery kit means losing access — that's the point."),("🔍","Open source","Komboe's source code is public on GitHub so anyone can review how it works.")])}</div></section>
<section class="band"><div class="wrap"><h2>One account, every device</h2><p class="lead">One Komboe account, one sign-in, on every device. You sign in with your email and master password (optionally a passkey and 2FA). Your master password is used on your device to derive the keys that decrypt your vault, so it is never sent to our servers.</p></div></section>
<section id="self-hosting"><div class="wrap"><h2>Self-hosting and outside services</h2><p class="lead">{SH_LONG} {SWITCH}.</p></div></section>'''
tiers=[("Free","$0","Personal starter",["Unlimited passwords","1 device type","Passkeys"]),("Plus","Coming soon","",["All devices","Secure sharing","Vault health report"]),("Family","Coming soon","",["Up to 6 members","Shared collections","Everything in Plus"]),("Business","Coming soon","",["Org admin console","AI agent integration (MCP)","Compliance reports"])]
pricing='<section class="hero"><div class="wrap"><h1>Pricing</h1><p>Simple plans for individuals, families and teams.</p><p class="sso">Paid plan prices will be announced at launch.</p></div></section><section><div class="wrap"><h2>Plans</h2><div class="grid">'+"".join(f'<div class="card{" hl" if n=="Plus" else ""}"><h3>{n}</h3><div class="price">{p} <small>{s}</small></div><ul>{"".join(f"<li>{x}</li>" for x in L)}</ul><a class="btn{" p" if n=="Plus" else ""} full" href="signup.html">Choose {n}</a></div>' for n,p,s,L in tiers)+'</div></div></section>'
PH='<span class="meta">Version and SHA-256 checksum will be published with the first release.</span>'
def dl(os_,icon,t,desc,btn,instr="",soon=False):
    b=f'<span class="btn full" aria-disabled="true">Coming soon</span>' if soon else f'<span class="btn full" aria-disabled="true">{btn}: coming soon</span>'
    return f'<div class="card dl{" soon" if soon else ""}" data-os="{os_}"><span class="tag">★ Detected for you</span><div class="ic">{icon}</div><h3>{t}</h3><p>{desc}</p>{instr}{"" if soon else PH}{b}</div>'
groups=[("Mobile",[dl("android","🤖","Android","Android 9+. Autofill service and biometric unlock.","Get it for Android"),dl("ios","🍎","iOS","iPhone and iPad.","",soon=True)]),
("Desktop",[dl("windows","🪟","Windows","Windows 10/11, x64 &amp; ARM64 installer.","Download .exe"),dl("macos","🍏","macOS","macOS 12+, Apple silicon &amp; Intel.","Download .dmg"),dl("linux","🐧","Linux","AppImage, .deb and .rpm.","Download for Linux")]),
("Browser extensions",[dl("ext-"+b.lower(),"🧩",b,f"Autofill and save logins in {b}.","Add to "+b) for b in ["Chrome","Edge","Firefox","Brave","Safari"]]),
("Web, CLI, server &amp; agents",[f'<div class="card dl" data-os="web"><div class="ic">🌐</div><h3>Web vault</h3><p>No install. Open in any modern browser.</p><a class="btn p full" href="login.html">Open web vault</a></div>',
dl("cli","⌨️","Command-line tool","<code>komboe</code> CLI and <code>komboe-run</code> for scripts and CI.","Download CLI",'<pre># install command coming soon\ncurl -fsSL https://komboe.com/install.sh | sh</pre>'),
dl("server","🗄️","Self-host server","Run your own Komboe sync server (Docker image).","Get server",'<pre># coming soon\ndocker pull ghcr.io/godeskio/komboe-server:TBD</pre><p style="font-size:13px"><b>Accounts:</b> local Komboe accounts by default; optional enterprise SSO via OIDC or SAML (e.g. Keycloak, Okta).</p><p style="font-size:13px">'+SH_SHORT+' '+SWITCH+'.</p>'),
dl("mcp","✨","AI agent integration (MCP)","MCP server giving AI agents scoped, revocable access to approved secrets.","Get MCP server",'<pre># MCP client config coming soon config\n{"mcpServers":{"komboe":{"command":"komboe","args":["mcp"]}}}</pre>')])]
downloads='<section class="hero"><div class="wrap"><h1>Download Komboe</h1><p>Every Komboe tool, on every platform. We detected: <b id="detected">…</b></p><p class="sso">Komboe is pre-release. Installers will appear here when the first builds are published.</p></div></section>'+"".join(f'<section style="padding:32px 0"><div class="wrap"><h2>{g}</h2><div class="grid">{"".join(c)}</div></div></section>' for g,c in groups)+'<section><div class="wrap"><p class="lead">Always verify the SHA-256 checksum of a download before installing: <code>sha256sum &lt;file&gt;</code> (Linux), <code>shasum -a 256 &lt;file&gt;</code> (macOS), <code>Get-FileHash &lt;file&gt;</code> (Windows).</p></div></section>'
VAULT_LOGIN="/vault"          # PLACEHOLDER web vault login (alternative: https://app.komboe.com)
VAULT_SIGNUP="/vault/signup"  # PLACEHOLDER web vault sign-up
def auth(mode):
    sg=mode=="signup"
    return f"""<div class="auth"><img src="assets/img/logo-96.webp" alt="Komboe logo" width="52" height="52"><h1>{"Create your Komboe account" if sg else "Log in to Komboe"}</h1>
<p>{"One Komboe account syncs and protects all your devices and apps: web vault, browser extensions, Android, desktop, CLI and the MCP agent integration." if sg else "Log in once with your Komboe account to reach your vault on every device: web, browser extensions, Android, desktop, CLI and MCP."}</p>
<ul class="steps"><li>{"Choose your email and a strong master password" if sg else "Enter your email and master password"}</li><li>{"Optionally add a passkey and two-factor authentication" if sg else "Or use your passkey; confirm with 2FA if enabled"}</li><li>Your vault is decrypted on your device only</li></ul>
<a class="btn p full" href="{VAULT_SIGNUP if sg else VAULT_LOGIN}">{"Create account in the web vault" if sg else "Open the web vault to log in"}</a>
<p class="sso">🔒 This marketing site never collects passwords. Your master password never leaves your device, and no admin can reset it.</p>
<p class="sso">{'Already have an account? <a href="login.html">Log in</a>' if sg else 'New here? <a href="signup.html">Create an account</a>'}</p></div>"""
GITGOAT_URL=os.environ.get("GITGOAT_URL","")  # empty = mirror link hidden
dev='<section class="hero"><div class="wrap"><h1>Developers</h1><p>Komboe is open source. Build on it, self-host it, and help make it better.</p><div class="cta"><a class="btn p" href="https://github.com/GoDeskio/Komboe">Komboe on GitHub</a>'+(f'<a class="btn" href="{GITGOAT_URL}">GitGoat mirror</a>' if GITGOAT_URL else '')+'</div></div></section><section><div class="wrap"><h2>Resources</h2>'+cards([("🗄️","Self-host docs","Run your own Komboe server with Docker. Local Komboe accounts by default, with optional enterprise SSO (OIDC/SAML). See <a href=\"https://github.com/GoDeskio/Komboe/tree/main/docs\">docs/</a> in the repo."),("⌨️","CLI","<code>komboe</code> and <code>komboe-run</code>: script your vault and inject secrets into processes via <code>komboe://item/field</code> references."),("✨","MCP / AI agents","Run <code>komboe mcp</code> to give AI agents scoped, revocable access to approved secrets."),("🧮","Encryptoglyph","The crypto library behind Komboe: <a href=\"https://github.com/GoDeskio/Encryptoglyph\">Encryptoglyph on GitHub</a> (Apache-2.0)."),("🤝","Contribute","Fork the repo, create a branch, and open a pull request. Open an issue first for larger changes."),("🛡️","Report a security issue","Please disclose responsibly: email <b>security@komboe.com</b> (placeholder — TBD) and do not open public issues for vulnerabilities. Give us reasonable time to fix before disclosure.")])+'</div></section>'
FAQ_ITEMS=[("What is a Komboe account?","One Komboe account syncs and protects all your devices and apps: the web vault, browser extensions, Android, desktop, CLI and the MCP agent integration. You sign in once with your email and master password, optionally with a passkey and two-factor authentication."),
("Does Komboe ever see my master password?","No. Komboe is zero-knowledge: your master password never leaves your device and your vault is encrypted before it syncs."),
("Can an admin reset my master password?","No. There is no backdoor and no admin password reset. Keep your recovery kit safe."),
("Does this website ask for my password?","No. Log in and sign up happen in the Komboe web vault, never on these marketing pages."),
("What about self-hosting?","Self-hosted servers use local Komboe accounts by default. Organizations can optionally add enterprise SSO via OIDC or SAML for sign-in; vault decryption still requires each user's master password. "+SH_LONG)]
FAQ='<section id="accounts"><div class="wrap"><h2>Accounts &amp; sign-in FAQ</h2><div class="grid">'+"".join(f'<div class="card"><h3>{q}</h3><p>{a}</p></div>' for q,a in FAQ_ITEMS)+'</div></div></section>'
home+=FAQ;security+=FAQ
pages_extra=1
VAULT=lambda sg,pre:f'''<section class="hero"><div class="wrap"><img src="{pre}assets/img/logo-96.webp" alt="Komboe logo" width="52" height="52"><h1>{"Web vault sign-up" if sg else "Web vault"} coming soon</h1><p>The Komboe web vault is not live yet. When it launches, {"you will create" if sg else "you will sign in to"} your one Komboe account here with your email and master password, plus optional passkey and 2FA.</p><div class="cta"><a class="btn p" href="{pre}downloads.html">See platforms</a><a class="btn" href="{pre}index.html">Home</a></div></div></section>'''
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'legal_copy.py')).read())
pages={"index.html":("Zero-knowledge password manager",home),"features.html":("Features",features),"security.html":("Security",security),"pricing.html":("Pricing",pricing),"downloads.html":("Downloads",downloads),"developers.html":("Developers",dev),"login.html":("Log in",auth("login")),"signup.html":("Sign up",auth("signup")),"privacy.html":("Privacy",PRIV),"terms.html":("Terms",TERMS)}
META={"index.html":("Zero-knowledge password manager","Komboe is an open-source, zero-knowledge password manager. Encryptoglyph encryption, no backdoor, no admin password reset. One account.",None),
"features.html":("Features","Every Komboe feature (vault, passkeys, sharing, browser extensions, desktop, Android, CLI, AI agent MCP integration) and the projects that inspired them.","Features"),
"security.html":("Security & zero-knowledge","How Komboe keeps your vault zero-knowledge: on-device Encryptoglyph encryption before upload, no backdoor and no admin password reset.","Security"),
"pricing.html":("Pricing","Komboe plans for individuals, families and businesses. Free tier available; paid prices to be announced.","Pricing"),
"downloads.html":("Downloads","Download Komboe for Android, Windows, macOS, Linux, Chrome, Edge, Firefox, Brave, Safari, the web, CLI, self-host server and MCP.","Downloads"),
"developers.html":("Developers","Komboe developer resources: source code, self-hosting, CLI, MCP server, Encryptoglyph (Apache-2.0), contributing and security disclosure.","Developers"),
"login.html":("Log in","Log in to Komboe: one account for the web vault, extensions, Android, desktop, CLI and MCP.","Log in"),
"signup.html":("Sign up","Create your Komboe account with your email and master password, plus optional passkey and 2FA.","Sign up"),
"privacy.html":("Privacy Policy (draft)","Draft Komboe privacy policy from GODESK IO LLC: what data we collect, why, your rights, and how your vault stays encrypted. Pending legal review.","Privacy"),
"terms.html":("Terms of Service (draft)","Draft Komboe terms of service for the hosted password manager. Pending legal review.","Terms")}
FAQ_LD={"@context":"https://schema.org","@type":"FAQPage","mainEntity":[{"@type":"Question","name":q,"acceptedAnswer":{"@type":"Answer","text":a.replace("<code>","").replace("</code>","")}} for q,a in FAQ_ITEMS]}
APP={"@context":"https://schema.org","@type":"SoftwareApplication","name":"Komboe","applicationCategory":"SecurityApplication","operatingSystem":"Android, Windows, macOS, Linux, Web","url":BASE+"/","publisher":{"@type":"Organization","name":"Komboe"},"offers":[{"@type":"Offer","name":"Free","price":"0","priceCurrency":"USD","url":BASE+"/pricing.html"}]}  # paid tiers omitted until real prices exist
WEBSITE={"@context":"https://schema.org","@type":"WebSite","name":"Komboe","url":BASE+"/","inLanguage":"en"}
EXTRA={"index.html":[WEBSITE,APP,FAQ_LD],"security.html":[FAQ_LD],"pricing.html":[APP]}
for fn,(t,b) in pages.items():
    title,desc,cr=META[fn]; open(fn,"w").write(page(fn,title,b,"",desc,cr,EXTRA.get(fn,())))
open("404.html","w").write(page("404.html","Page not found",'<section class="hero"><div class="wrap"><h1>Page not found</h1><p>That page does not exist.</p><div class="cta"><a class="btn p" href="/index.html">Home</a><a class="btn" href="/features.html">Features</a><a class="btn" href="/downloads.html">Downloads</a></div></div></section>',"/","Page not found."))
def u(f): return BASE+("/" if f=="index.html" else "/"+f)
open("sitemap.xml","w").write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'+"".join(f'<url><loc>{u(f)}</loc><xhtml:link rel="alternate" hreflang="en" href="{u(f)}"/><xhtml:link rel="alternate" hreflang="x-default" href="{u(f)}"/></url>\n' for f in pages if f not in ("privacy.html","terms.html"))+'</urlset>\n')
open("robots.txt","w").write("User-agent: *\nDisallow: /\n" if STAGING else f"User-agent: *\nAllow: /\nSitemap: {BASE}/sitemap.xml\n")

os.makedirs("vault/signup",exist_ok=True)
open("vault/index.html","w").write(page("vault/index.html","Web vault coming soon",VAULT(False,"../"),"../","The Komboe web vault is coming soon."))
open("vault/signup/index.html","w").write(page("vault/signup/index.html","Web vault sign-up coming soon",VAULT(True,"../../"),"../../","Komboe web vault sign-up is coming soon."))
os.makedirs(".well-known",exist_ok=True)
import datetime as _d
open(".well-known/security.txt","w").write("# Contact address is a placeholder (TBD): confirm security@komboe.com is monitored before launch.\nContact: mailto:security@komboe.com\nExpires: "+(_d.datetime.now(_d.timezone.utc)+_d.timedelta(days=365)).strftime("%Y-%m-%dT00:00:00Z")+"\nPreferred-Languages: en\nCanonical: "+BASE+"/.well-known/security.txt\nPolicy: "+BASE+"/developers.html#security\n")
open("llms.txt","w").write(("# Komboe\n\n> Komboe is an open-source, zero-knowledge password manager (pre-release). Vaults are encrypted on-device with Encryptoglyph (Apache-2.0); vault contents are end-to-end encrypted on the device before upload, so Komboe can't read vault data; some account metadata is processed as described in the Privacy Policy (https://komboe.com/privacy.html). The master password never leaves the device, there is no backdoor and no admin password reset. One Komboe account (email + master password, optional passkey and 2FA) covers the web vault, browser extensions, Android, desktop, CLI and an MCP agent integration. iOS is planned. Paid prices and release builds are not yet published.\n\n## Pages\n"+"".join(f"- [{META[f][0]}]({u(f)}): {META[f][1]}\n" for f in pages)+"\n## Self-hosting\n"+SH_LONG+" Switches: "+RUNNING+"\n\n## Source\n- [GitHub](https://github.com/GoDeskio/Komboe)\n").replace("<code>","`").replace("</code>","`"))
os.makedirs("downloads",exist_ok=True)
