#!/usr/bin/env python3
"""Komboe rebrand pass over vendored upstream trees (idempotent).

User-visible strings and artwork only. Protocol/API identifiers (headers, package
names, `@bitwarden/*` imports, URL paths, enum names) are left alone so clients
stay wire-compatible. Copyright and license text is never touched.
The padlock-K logo is used as-is from branding/logo (shape locked).
"""
import base64, glob, io, json, os, re, shutil, sys
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C, S, B = (os.path.join(ROOT, p) for p in ("clients/upstream", "server/upstream", "branding/logo"))
WORD = re.compile(r"\b(Bitwarden|Vaultwarden)\b")
PROTECT = re.compile(r"copyright|licen[cs]e|@bitwarden|bitwarden_|\.bitwarden\.|github\.com", re.I)
changed = []

def rw(path, fn):
    with open(path, encoding="utf-8", newline="") as f: old = f.read()
    new = fn(old)
    if new != old:
        with open(path, "w", encoding="utf-8", newline="") as f: f.write(new)
        changed.append(os.path.relpath(path, ROOT))

def sub_line(line):
    return line if PROTECT.search(line) else WORD.sub("Komboe", line)

def sub_text(t):
    return "".join(sub_line(l) for l in t.splitlines(keepends=True))

# 1. locale message values (web + shared libs). Only "message" values change.
def locale(t):
    return "".join(WORD.sub("Komboe", l).replace("bitwarden.com", "komboe.com") if '"message":' in l else l
                   for l in t.splitlines(keepends=True))
for p in glob.glob(f"{C}/apps/web/src/locales/*/messages.json") + glob.glob(f"{C}/apps/cli/src/locales/*/messages.json"):
    rw(p, locale)

# 2. page titles / PWA manifest
BLUE = re.compile(r"#175DDC", re.I)
for p in [f"{C}/apps/web/src/index.html", f"{C}/apps/web/src/404.html", f"{C}/apps/web/src/connectors/**/*.html"]:
    for q in glob.glob(p, recursive=True): rw(q, lambda t: BLUE.sub("#0B1F3A", sub_text(t)))
rw(f"{C}/apps/web/src/manifest.json", lambda t: t.replace('"Bitwarden Vault"', '"Komboe Vault"')
   .replace("#175DDC", "#0B1F3A"))

# 2b. browser extension, desktop and CLI: locale strings, product names, theme color
for p in (glob.glob(f"{C}/apps/browser/src/_locales/*/messages.json") + glob.glob(f"{C}/apps/desktop/src/locales/*/messages.json")):
    rw(p, locale)
for p in [f"{C}/apps/desktop/electron-builder.json", f"{C}/apps/desktop/src/package.json"]:
    rw(p, lambda t: BLUE.sub("#0B1F3A", t.replace('"productName": "Bitwarden"', '"productName": "Komboe"')
                              .replace('"name": "Bitwarden",', '"name": "Komboe",')))
for p in glob.glob(f"{C}/apps/browser/src/**/*.html", recursive=True):
    rw(p, lambda t: BLUE.sub("#0B1F3A", t))

# 3. artwork: padlock-K PNG (unchanged shape) at each size upstream used
def png(src, size):
    im = Image.open(src).convert("RGBA"); im.thumbnail(size, Image.LANCZOS)
    canvas = Image.new("RGBA", size, (0, 0, 0, 0)); canvas.paste(im, ((size[0]-im.width)//2, (size[1]-im.height)//2), im)
    b = io.BytesIO(); canvas.save(b, "PNG", optimize=True); return b.getvalue()
ICON = f"{B}/master/komboe-logo-master-transparent.png"
LIGHT = f"{B}/variants/komboe-light-transparent.png"
DARK = f"{B}/variants/komboe-dark-transparent.png"
targets = {f"{C}/apps/web/src/images/icons/*.png": ICON, f"{C}/apps/web/src/images/logo-dark@2x.png": DARK,
           f"{C}/apps/web/src/images/logo-primary@2x.png": DARK, f"{C}/apps/web/src/images/logo-white@2x.png": LIGHT,
           f"{S}/src/static/images/vaultwarden-icon.png": ICON, f"{S}/src/static/images/vaultwarden-favicon.png": ICON,
           f"{S}/src/static/images/logo-gray.png": LIGHT,
           f"{C}/apps/browser/src/images/icon*.png": ICON, f"{C}/apps/desktop/resources/icon.png": ICON,
           f"{C}/apps/desktop/resources/icons/*.png": ICON}
for pat, src in targets.items():
    for p in glob.glob(pat):
        new = png(src, Image.open(p).size)
        if "_gray" in os.path.basename(p):  # disabled-state icons stay grey (same shape)
            im = Image.open(io.BytesIO(new)); g = im.convert("LA").convert("RGBA"); b = io.BytesIO(); g.save(b, "PNG", optimize=True); new = b.getvalue()
        if open(p, "rb").read() != new:
            open(p, "wb").write(new); changed.append(os.path.relpath(p, ROOT))

_SORA = {}
def sora_path(text, h, x0, avail):
    """'Komboe' in Sora SemiBold (OFL, branding/fonts/sora) as outlined SVG path: cap height 56% of h, vertically centred."""
    from fontTools.ttLib import TTFont
    from fontTools.varLib import instancer
    from fontTools.pens.svgPathPen import SVGPathPen
    from fontTools.pens.transformPen import TransformPen
    from fontTools.pens.boundsPen import BoundsPen
    if not _SORA:
        f = instancer.instantiateVariableFont(TTFont(os.path.join(B, "../fonts/sora/Sora-Variable.ttf")), {"wght": 600})
        _SORA["gs"], _SORA["cmap"], _SORA["upm"] = f.getGlyphSet(), f.getBestCmap(), f["head"].unitsPerEm
    gs, cmap, upm = _SORA["gs"], _SORA["cmap"], _SORA["upm"]
    bp = BoundsPen(gs); gs[cmap[ord("K")]].draw(bp); cap = bp.bounds[3]
    adv = sum(gs[cmap[ord(c)]].width - 0.012 * upm for c in text)
    sc = min(0.56 * h / cap, avail / adv); x, base, out = x0, h / 2 + cap * sc / 2, []
    for c in text:
        g = gs[cmap[ord(c)]]; pen = SVGPathPen(gs, ntos=lambda v: f"{v:.1f}")
        g.draw(TransformPen(pen, (sc, 0, 0, -sc, x, base))); out.append(pen.getCommands()); x += (g.width - 0.012 * upm) * sc
    return " ".join(out)

def mark_g(h, attr):
    """Padlock-K vector (branding/logo/master/komboe-logo.svg), uniformly scaled to height h; shape untouched, color only."""
    d = re.search(r'd="([^"]+)"', open(f"{B}/master/komboe-logo.svg").read()).group(1)
    return f'<g transform="scale({h / 1928:.6f}) translate(-468,-196)"><path{attr} d="{d}" transform="translate(1121,196)"/></g>'

def logo_svg(viewbox, wordmark=True, cls="tw-fill-fg-nav", mark="#6D4AFF", ink="#16122B"):
    _, _, w, h = (float(x) for x in viewbox.split())
    attr = f' class="{cls}"' if cls else f' fill="{ink}"'
    text = f'<path{attr} d="{sora_path("Komboe", h, h * 1.0, w - h * 1.05)}"/>' if wordmark else ""
    m = mark_g(h, attr if cls else f' fill="{mark}"')
    return (f'<svg viewBox="{viewbox}" xmlns="http://www.w3.org/2000/svg">'
            f'<title>Komboe</title>{m}{text}</svg>')

def svg_ts(t):
    def rep(m):
        vb = re.search(r'viewBox="([^"]+)"', m.group(1))
        if not vb: return m.group(0)
        _, _, w, h = (float(x) for x in vb.group(1).split())
        return "svg`\n  " + logo_svg(vb.group(1), wordmark=w > h * 1.6) + "\n`"
    return re.sub(r"svg`\s*(<svg.*?</svg>)\s*`", rep, t, flags=re.S)
for n in ["bitwarden-logo.icon.ts", "bitwarden-logo-beta.icon.ts", "password-manager.ts", "side-nav-logo.ts",
          "side-nav-logo-beta.ts", "shield.ts"]:
    p = f"{C}/libs/assets/src/svg/svgs/{n}"
    if os.path.exists(p): rw(p, svg_ts)
for p, mk, ink in [(f"{C}/apps/web/src/images/logo.svg", "#6D4AFF", "#16122B"), (f"{C}/apps/web/src/images/logo-white.svg", "#FFFFFF", "#FFFFFF")]:
    if os.path.exists(p):
        rw(p, lambda t, mk=mk, ink=ink: logo_svg(re.search(r'viewBox="([^"]+)"', t).group(1), cls="", mark=mk, ink=ink) + "\n"
           if re.search(r'viewBox="([^"]+)"', t) else t)

# 4. server user-visible templates (admin UI, emails, 404)
for p in glob.glob(f"{S}/src/static/templates/**/*.hbs", recursive=True):
    rw(p, sub_text)

# 5. Phase C: violet theme, CLI name/data dir, product switcher, footer product line
VIOLET = {"050": "#f4f1ff", "100": "#ebe5ff", "200": "#d9ceff", "300": "#c4b7ff", "400": "#a48dff",
          "500": "#7c5cff", "600": "#6d4aff", "700": "#5a36f0", "800": "#4a28c9", "900": "#3e24b4", "950": "#24166b"}
RGB = lambda h: ", ".join(str(int(h[i:i+2], 16)) for i in (1, 3, 5))
def theme(t):
    for k, v in VIOLET.items():
        t = re.sub(rf"(--color-brand-{k}:\s*)#[0-9a-fA-F]{{6}}", rf"\g<1>{v}", t)
        t = re.sub(rf"(--color-brand-{k}-rgb:\s*)[0-9, ]+;", rf"\g<1>{RGB(v)};", t)
    return t
rw(f"{C}/libs/components/src/tw-theme.css", theme)
rw(f"{C}/apps/cli/src/service-container/service-container.ts", lambda t: t.replace('"Bitwarden CLI"', '"Komboe CLI"')
   .replace('Support/Bitwarden CLI"', 'Support/Komboe CLI"').replace('".config/Bitwarden CLI"', '".config/Komboe CLI"'))
def clipkg(t):
    t = t.replace('"bw": "build/bw.js"', '"komboe": "build/bw.js"')
    return re.sub(r'(--output \./dist/[^"]*/)bw(\.exe)?"', r'\1komboe\2"', t)
rw(f"{C}/apps/cli/package.json", clipkg)
rw(f"{C}/apps/web/src/app/layouts/product-switcher/shared/product-switcher.service.ts", lambda t: t.replace(
   "        if (smOrg) {\n          bento.push(products.sm);\n        } else if (!shouldDisableSMAds) {\n          // Only show SM in \"other\" section if ads are not disabled\n          other.push(products.sm);\n        }\n",
   "        // Komboe: Secrets Manager is not part of Komboe; never offered in the switcher.\n        void smOrg;\n        void shouldDisableSMAds;\n"))
FOOT = '<div bitTypography="body2">&copy; {{ year }} Bitwarden Inc.</div>'
for p in [f"{C}/apps/web/src/app/layouts/frontend-layout.component.html", f"{C}/libs/components/src/anon-layout/anon-layout.component.html"]:
    rw(p, lambda t: t.replace(FOOT, '<div bitTypography="body2">Komboe</div>\n' + FOOT) if '>Komboe</div>' not in t else t)

# 6. Phase C branding gaps: no Bitwarden cloud regions in the server picker, violet autofill icons, Android label
ENV = f"{C}/libs/angular/src/auth/environment-selector/environment-selector.component.html"
def envsel(t):
    if 'Komboe: Bitwarden-hosted regions' in t: return t
    t = t.replace('      <button\n        *ngFor="let region of availableRegions$ | async; let i = index"',
                  '      <!-- Komboe: Bitwarden-hosted regions are not offered; Komboe is self-hosted only -->\n'
                  '      <ng-container *ngIf="false">\n      <button\n        *ngFor="let region of availableRegions$ | async; let i = index"')
    t = t.replace('        <span>{{ region.domain }}</span>\n      </button>\n', '        <span>{{ region.domain }}</span>\n      </button>\n      </ng-container>\n', 1)
    return t.replace('data.selectedRegion?.domain || ("selfHostedServer" | i18n)',
                     'data.selectedRegion ? ("komboeChooseServer" | i18n) : ("selfHostedServer" | i18n)')
rw(ENV, envsel)
def addmsg(t):
    if '"komboeChooseServer"' in t: return t
    i = t.rstrip().rfind("}"); j = t.rstrip()[:i].rstrip()
    return j + ',\n  "komboeChooseServer": {\n    "message": "Choose your Komboe server"\n  }\n}\n'
for p in [f"{C}/apps/browser/src/_locales/en/messages.json", f"{C}/apps/web/src/locales/en/messages.json", f"{C}/apps/desktop/src/locales/en/messages.json"]:
    rw(p, addmsg)
for p in glob.glob(f"{C}/apps/browser/src/autofill/**/*", recursive=True):
    if os.path.isfile(p) and re.search(r"\.(ts|scss|css|html|snap)$", p) and ".stories." not in p:
        rw(p, lambda t: re.sub(r"#175ddc", "#6D4AFF", t, flags=re.I))

# 7. Desktop (Electron) identity: own app id and launcher name (no Bitwarden desktop id collisions)
def ebuilder(t):
    d = json.loads(t); d["appId"] = "io.komboe.desktop"
    d.setdefault("linux", {}).setdefault("desktop", {}).setdefault("entry", {})["Name"] = "Komboe"
    d["linux"]["desktop"]["entry"]["StartupWMClass"] = "komboe"   # must match the runtime WM_CLASS (case-sensitive)
    d["linux"]["executableName"] = "komboe"
    d.setdefault("extraMetadata", {})["name"] = "komboe"   # Electron app name -> Linux WM_CLASS / userData dir
    d.setdefault("deb", {})["packageName"] = "komboe"
    d["linux"]["synopsis"] = "Komboe: open-source, zero-knowledge password manager."
    return json.dumps(d, indent=2) + "\n"
rw(f"{C}/apps/desktop/electron-builder.json", ebuilder)
rw(f"{C}/apps/desktop/src/package.json", lambda t: t.replace('"desktopName": "bitwarden.desktop"', '"desktopName": "komboe.desktop"'))
rw(f"{C}/apps/desktop/src/index.html", lambda t: t.replace("<title>Bitwarden</title>", "<title>Komboe</title>"))

# 8. Phase D: padlock-K everywhere icons remain upstream: extension inline-menu/notification logo, desktop ico/icns/iconsets
def pk_svg(size, gray=False):
    data = base64.b64encode(png(LIGHT, (64, 64))).decode()  # violet #6D4AFF padlock-K
    f = ('<filter id="g"><feColorMatrix type="saturate" values="0"/></filter>' if gray else "")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 {size} {size}" fill="none">{f}'
            f'<image width="{size}" height="{size}" {"filter=\"url(#g)\" " if gray else ""}href="data:image/png;base64,{data}"/></svg>')
def svgicons(t):
    out = []
    lines = t.split("\n"); i = 0
    while i < len(lines):
        out.append(lines[i])
        m = re.match(r"export const (logoIcon|logoLockedIcon) =$", lines[i])
        if m: out.append("  '" + pk_svg(14 if m.group(1) == "logoIcon" else 16, gray=m.group(1) == "logoLockedIcon") + "';"); i += 1
        i += 1
    return "\n".join(out)
rw(f"{C}/apps/browser/src/autofill/utils/svg-icons.ts", svgicons)
KIT = f"{B}/desktop"
def copyfile(src, dst):
    if os.path.exists(dst) and open(src, "rb").read() == open(dst, "rb").read(): return
    shutil.copyfile(src, dst); changed.append(os.path.relpath(dst, ROOT))
R = f"{C}/apps/desktop/resources"
for n in ["icon.ico", "icon.beta.ico"]: copyfile(f"{KIT}/komboe.ico", f"{R}/{n}")
for n in ["icon.icns", "icon.beta.icns", "dmg.icns", "dmg.beta.icns"]: copyfile(f"{KIT}/komboe.icns", f"{R}/{n}")
for p in glob.glob(f"{R}/icon.iconset/*.png") + glob.glob(f"{R}/dmg.iconset/*.png") + glob.glob(f"{R}/icons_beta/*.png") + [f"{R}/icon.beta.png"]:
    if os.path.exists(p):
        new = png(ICON, Image.open(p).size)
        if open(p, "rb").read() != new: open(p, "wb").write(new); changed.append(os.path.relpath(p, ROOT))
for p in glob.glob(f"{R}/windows_plugin_authenticator_logo_*.svg"): rw(p, lambda t: pk_svg(48))

if "-v" in sys.argv: print("\n".join(changed))

# 9. Phase E: self-hosted Sora (SIL OFL 1.1) brand font for display headings; the wordmark itself is outlined paths (step 3)
WF = f"{C}/libs/components/src/webfonts"
if os.path.isdir(WF):
    src = os.path.join(B, "../fonts/sora/Sora-Variable.woff2")
    for n, fn in (("sora.woff2", src), ("SORA-OFL.txt", os.path.join(B, "../fonts/sora/OFL.txt"))):
        dst = os.path.join(WF, n)
        if not os.path.exists(dst) or open(dst, "rb").read() != open(fn, "rb").read(): shutil.copyfile(fn, dst); changed.append(dst)
FACE = ('@font-face {\n  font-family: Sora;\n  src: url("~@bitwarden/components/src/webfonts/sora.woff2") format("woff2") tech(variations),\n'
        '    url("~@bitwarden/components/src/webfonts/sora.woff2") format("woff2-variations");\n  font-display: swap;\n  font-weight: 100 800;\n}\n'
        ':root { --font-brand: Sora, Inter, ui-sans-serif, system-ui, sans-serif; }\nh1, .komboe-brand { font-family: var(--font-brand); letter-spacing: -0.01em; }\n')
rw(f"{C}/libs/components/src/theme.css", lambda t: t if "font-family: Sora" in t else t.replace("@font-face {\n  font-family: Inter;", FACE + "\n@font-face {\n  font-family: Inter;", 1))

# 10. Phase F: desktop package metadata + URL scheme. Windows VersionInfo CompanyName/LegalCopyright come from
# package.json "author" and electron-builder "copyright"; deb Maintainer/Vendor from "author"/"homepage".
# Desktop deep links move from bitwarden:// to komboe:// so Komboe never claims the Bitwarden desktop scheme.
# Upstream copyright stays in LICENSE/NOTICE/README credit; only this product's own metadata changes.
D = f"{C}/apps/desktop"
def ebuilder2(t):
    d = json.loads(t)
    d["copyright"] = "Copyright \u00a9 2026 GoDesk. Komboe is based on Bitwarden clients (GPL-3.0)."
    d.setdefault("win", {}).setdefault("signtoolOptions", {})["publisherName"] = "GoDesk"
    a = d.setdefault("appx", {})
    a.update(applicationId="komboedesktop", identityName="GoDesk.Komboe", publisher="CN=GoDesk",
             publisherDisplayName="GoDesk", displayName="Komboe")
    if "mas" in d: d["mas"]["identity"] = "GoDesk"
    if "snap" in d:
        d["snap"]["summary"] = "Komboe is a secure, self-hosted password manager for all of your devices."
        d["snap"]["description"] = "Password Manager\n**Installation**\nKomboe requires access to the `password-manager-service`. Run `sudo snap connect komboe:password-manager-service` after installation."
    if isinstance(d.get("publish"), dict) and "bitwarden.com" in d["publish"].get("url", ""):
        d["publish"]["url"] = "https://downloads.komboe.com/desktop"   # never pull Bitwarden auto-updates
    for pr in d.get("protocols", []):
        pr["name"] = "Komboe"; pr["schemes"] = ["komboe"]
    return json.dumps(d, indent=2, ensure_ascii=False) + "\n"
for p in [f"{D}/electron-builder.json", f"{D}/electron-builder.beta.json"]:
    if os.path.exists(p): rw(p, ebuilder2)
def pkg(t):
    d = json.loads(t)
    d["author"] = "GoDesk <hello@komboe.com> (https://komboe.com)"; d["homepage"] = "https://komboe.com"
    d["description"] = "Komboe: a secure, self-hosted password manager for all of your devices."
    return json.dumps(d, indent=2, ensure_ascii=False) + "\n"
rw(f"{D}/src/package.json", pkg)
SCHEME = lambda t: t.replace('"bitwarden://', '"komboe://').replace('ProtocolClient("bitwarden"', 'ProtocolClient("komboe"')
for p in [f"{D}/src/main.ts", f"{D}/src/app/app.component.ts",
          f"{C}/libs/auth/src/common/services/sso-redirect/sso-url.service.ts",
          f"{C}/libs/importer/src/components/lastpass/lastpass-direct-import.service.ts"]:
    if os.path.exists(p): rw(p, SCHEME)
# web Duo connector: desktop hand-off uses komboe://; mobile keeps its own scheme
rw(f"{C}/apps/web/src/connectors/duo-redirect.ts", lambda t: t.replace('const mobileDesktopCallback = "bitwarden://duo-callback";',
   'const mobileDesktopCallback = "komboe://duo-callback";'))

print(f"rebrand: {len(changed)} files changed")
