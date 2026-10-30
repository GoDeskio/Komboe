#!/usr/bin/env python3
"""Komboe rebrand pass over vendored upstream trees (idempotent).

User-visible strings and artwork only. Protocol/API identifiers (headers, package
names, `@bitwarden/*` imports, URL paths, enum names) are left alone so clients
stay wire-compatible. Copyright and license text is never touched.
The padlock-K logo is used as-is from branding/logo (shape locked).
"""
import base64, glob, io, json, os, re, sys
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

def logo_svg(viewbox, wordmark=True, cls="tw-fill-fg-nav"):
    _, _, w, h = (float(x) for x in viewbox.split())
    data = base64.b64encode(png(ICON, (96, 96))).decode()
    text = (f'<text x="{h*1.15:.1f}" y="{h*0.72:.1f}" font-family="Inter,Arial,sans-serif" font-weight="700" '
            f'font-size="{h*0.62:.1f}" class="{cls}">Komboe</text>') if wordmark else ""
    return (f'<svg viewBox="{viewbox}" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">'
            f'<title>Komboe</title><image x="0" y="0" width="{h:.1f}" height="{h:.1f}" href="data:image/png;base64,{data}"/>{text}</svg>')

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
for p in [f"{C}/apps/web/src/images/logo.svg", f"{C}/apps/web/src/images/logo-white.svg"]:
    if os.path.exists(p):
        rw(p, lambda t: logo_svg(re.search(r'viewBox="([^"]+)"', t).group(1), cls="") + "\n"
           if re.search(r'viewBox="([^"]+)"', t) else t)

# 4. server user-visible templates (admin UI, emails, 404)
for p in glob.glob(f"{S}/src/static/templates/**/*.hbs", recursive=True):
    rw(p, sub_text)

print(f"rebrand: {len(changed)} files changed")
if "-v" in sys.argv: print("\n".join(changed))
