#!/usr/bin/env python3
"""Komboe wordmark: padlock-K mark (unchanged vector trace, recolored only) + 'Komboe' set in Sora SemiBold (SIL OFL 1.1).
Text is converted to outlines so the SVGs need no font. Also emits self-hostable static Sora woff2/ttf files.
Usage: build_wordmark.py <out_dir>"""
import os, re, sys, subprocess
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.transformPen import TransformPen

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "out")
VF = os.path.join(ROOT, "fonts/sora/Sora-Variable.ttf"); MARK = os.path.join(ROOT, "logo/master/komboe-logo.svg")
if not os.path.exists(MARK): MARK = "/workspace/Grok Bot Projects/Brand/Komboe/master/komboe-logo.svg"
os.makedirs(OUT, exist_ok=True); FD = os.path.join(ROOT, "fonts/sora")
fonts = {}
for w, n in ((400, "Regular"), (600, "SemiBold"), (700, "Bold")):
    f = instancer.instantiateVariableFont(TTFont(VF), {"wght": w}); f.save(os.path.join(FD, f"Sora-{n}.ttf"))
    f.flavor = "woff2"; f.save(os.path.join(FD, f"Sora-{n}.woff2")); fonts[n] = TTFont(os.path.join(FD, f"Sora-{n}.ttf"))
font = fonts["SemiBold"]; gs = font.getGlyphSet(); cmap = font.getBestCmap(); upm = font["head"].unitsPerEm
TEXT, TRACK = "Komboe", -0.012   # slight negative tracking for a tight, premium feel
svgtxt = open(MARK).read(); md = re.search(r"<path[^>]*/>", svgtxt, re.S).group(0)   # single path, shape untouched
MX0, MY0, MW, MH = 468, 196, 1384, 1928    # mark bbox in the 2312-unit master
H = 512.0; ms = H / MH                      # mark height = canvas height
cap = gs[cmap[ord("K")]]; bp = BoundsPen(gs); cap.draw(bp); capH = bp.bounds[3]
size = 0.56 * H / capH * upm / upm          # cap height = 56% of mark height
scale = 0.56 * H / capH; gap = 0.30 * H
x = MW * ms + gap; base = H / 2 + capH * scale / 2
d = []
for ch in TEXT:
    g = gs[cmap[ord(ch)]]; p = SVGPathPen(gs)
    g.draw(TransformPen(p, (scale, 0, 0, -scale, x, base))); d.append(p.getCommands())
    x += (g.width + TRACK * upm) * scale
W = x - TRACK * upm * scale + 8
SCHEMES = {"light": ("#6D4AFF", "#16122B"), "dark": ("#C4B7FF", "#FFFFFF"), "mono-black": ("#070702", "#070702"), "mono-white": ("#FFFFFF", "#FFFFFF")}
def svg(mark, text, bg=None, pad=0):
    r = f'<rect x="{-pad}" y="{-pad}" width="{W+2*pad:.1f}" height="{H+2*pad:.1f}" rx="{pad*0.6:.0f}" fill="{bg}"/>' if bg else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{-pad} {-pad} {W+2*pad:.1f} {H+2*pad:.1f}" role="img" aria-label="Komboe">'
            f'<title>Komboe</title>{r}<g transform="scale({ms:.6f}) translate({-MX0},{-MY0})">{md.replace("#000000", mark)}</g>'
            f'<path fill="{text}" d="{" ".join(d)}"/></svg>\n')
for k, (mc, tc) in SCHEMES.items():
    open(os.path.join(OUT, f"komboe-wordmark-{k}.svg"), "w").write(svg(mc, tc))
open(os.path.join(OUT, "komboe-wordmark-light-on-bg.svg"), "w").write(svg("#6D4AFF", "#16122B", "#FFFFFF", 96))
open(os.path.join(OUT, "komboe-wordmark-dark-on-bg.svg"), "w").write(svg("#C4B7FF", "#FFFFFF", "#191724", 96))
for f in os.listdir(OUT):
    if f.endswith(".svg"):
        for hgt in (128, 512):
            subprocess.run(["convert", "-background", "none", "-density", "300", os.path.join(OUT, f), "-resize", f"x{hgt}",
                            os.path.join(OUT, f[:-4] + f"-{hgt}.png")], check=True)
print("wordmark ->", OUT, f"{W:.0f}x{H:.0f}")
