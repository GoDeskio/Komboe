#!/usr/bin/env python3
"""Komboe Android rebrand (idempotent): applicationId io.komboe.android, app name Komboe, padlock-K launcher.
Kotlin namespace/package names stay upstream (internal identifiers); copyright/license text untouched."""
import glob, os, re, sys
S = sys.argv[1]; ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def rw(p, fn):
    t = open(p, encoding="utf-8").read(); n = fn(t)
    if n != t: open(p, "w", encoding="utf-8").write(n); print("rebrand", os.path.relpath(p, S))
rw(f"{S}/app/build.gradle.kts", lambda t: t.replace('applicationId = "com.x8bit.bitwarden"', 'applicationId = "io.komboe.android"')
   .replace('archivesName.set("com.x8bit.bitwarden")', 'archivesName.set("io.komboe.android")')
   .replace('            applicationIdSuffix = ".dev"\n', ''))
for p in glob.glob(f"{S}/app/src/*/res/values/strings_non_localized.xml"):
    rw(p, lambda t: re.sub(r'(name="app_name"[^>]*>)(?:Bitwarden|Komboe)( Beta| Dev)?<', r"\1Komboe<", t))
for p in glob.glob(f"{S}/app/src/main/res/values*/strings.xml"):
    rw(p, lambda t: "".join(l if re.search(r"copyright|licen[cs]e|bitwarden\.com|@", l, re.I) else re.sub(r"\bBitwarden\b", "Komboe", l) for l in t.splitlines(True)))
try:
    from PIL import Image
    src = Image.open(f"{ROOT}/branding/logo/master/komboe-logo-master-transparent.png").convert("RGBA")
    for p in glob.glob(f"{S}/app/src/*/res/mipmap-*/*.png") + glob.glob(f"{S}/app/src/*/res/mipmap-*/*.webp"):
        im = Image.open(p); size = im.size; c = Image.new("RGBA", size, (255, 255, 255, 255))
        l = src.copy(); l.thumbnail((int(size[0]*.8), int(size[1]*.8))); c.paste(l, ((size[0]-l.width)//2, (size[1]-l.height)//2), l)
        c.save(p)
except ImportError: pass
# Phase D: adaptive launcher icon (mipmap-anydpi overrides the PNG mipmaps on API 26+) and in-app logos -> padlock-K.
# Compose painterResource only accepts vectors or rasters, so the vector XMLs are replaced by same-named PNGs (drawable-nodpi).
try:
    from PIL import Image
    src = Image.open(f"{ROOT}/branding/logo/master/komboe-logo-master-transparent.png").convert("RGBA")
    def put(xml, size, frac, mono=False):
        d = os.path.join(os.path.dirname(os.path.dirname(xml)), "drawable-nodpi"); os.makedirs(d, exist_ok=True)
        c = Image.new("RGBA", (size, size), (0, 0, 0, 0)); l = src.copy(); l.thumbnail((int(size*frac),) * 2)
        if mono: l = Image.merge("RGBA", (*[Image.new("L", l.size, 255)] * 3, l.getchannel("A")))
        c.paste(l, ((size-l.width)//2, (size-l.height)//2), l)
        c.save(os.path.join(d, os.path.basename(xml)[:-4] + ".png")); os.remove(xml); print("rebrand icon", os.path.relpath(xml, S))
    for x in glob.glob(f"{S}/app/src/*/res/drawable/ic_launcher_foreground.xml"): put(x, 432, .55)
    for x in glob.glob(f"{S}/app/src/*/res/drawable/ic_launcher_monochrome.xml"): put(x, 432, .55, mono=True)
    for n in ["logo_bitwarden", "logo_shield_icon", "logo_bitwarden_icon"]:
        for x in glob.glob(f"{S}/ui/src/main/res/drawable/{n}.xml"): put(x, 512, 1.0)
    for p in glob.glob(f"{S}/app/src/*/res/values/ic_launcher_background.xml"):
        rw(p, lambda t: re.sub(r"(<color name=\"ic_launcher_background\">)[^<]*<", r"\1#FFFFFF<", t))
except ImportError: pass
