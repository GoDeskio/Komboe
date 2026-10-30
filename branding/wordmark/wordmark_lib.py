"""Shared wordmark geometry: padlock-K vector (shape untouched) + 'Komboe' in Sora SemiBold (SIL OFL 1.1) as outlines."""
import os, re
HERE = os.path.dirname(os.path.abspath(__file__)); BR = os.path.dirname(HERE)
MARK_BBOX = (468, 196, 1384, 1928)        # x, y, w, h of the glyph in the 2312-unit master
def mark_d():
    return re.search(r'd="([^"]+)"', open(os.path.join(BR, "logo/master/komboe-logo.svg")).read()).group(1)   # drawn at translate(1121,196)
def text_d(h, x0, avail, text="Komboe", weight=600, track=-0.012):
    from fontTools.ttLib import TTFont
    from fontTools.varLib import instancer
    from fontTools.pens.svgPathPen import SVGPathPen
    from fontTools.pens.transformPen import TransformPen
    from fontTools.pens.boundsPen import BoundsPen
    f = instancer.instantiateVariableFont(TTFont(os.path.join(BR, "fonts/sora/Sora-Variable.ttf")), {"wght": weight})
    gs, cmap, upm = f.getGlyphSet(), f.getBestCmap(), f["head"].unitsPerEm
    bp = BoundsPen(gs); gs[cmap[ord("K")]].draw(bp); cap = bp.bounds[3]
    adv = sum(gs[cmap[ord(c)]].width + track * upm for c in text)
    sc = min(0.56 * h / cap, avail / adv); x, base, out = x0, h / 2 + cap * sc / 2, []
    for c in text:
        g = gs[cmap[ord(c)]]; pen = SVGPathPen(gs, ntos=lambda v: f"{v:.1f}")
        g.draw(TransformPen(pen, (sc, 0, 0, -sc, x, base))); out.append(pen.getCommands()); x += (g.width + track * upm) * sc
    return " ".join(out), x
def rel_d(d, q=1.0):
    """Compact SVG path: grid-rounded absolute points re-expressed as relative commands (aapt2 caps a string at 32 KB)."""
    from fontTools.svgLib.path import parse_path
    from fontTools.pens.recordingPen import RecordingPen
    r = RecordingPen(); parse_path(d, r); out = []; cx = cy = sx = sy = 0
    R = lambda v: round(v / q) * q if q != 1 else round(v)
    def seq(ns):
        s = ""
        for n in ns:
            t = (f"{n:.2f}".rstrip("0").rstrip(".") if isinstance(n, float) else str(n)); s += t if not s or t.startswith("-") else " " + t
        return s
    for op, pts in r.value:
        if op == "moveTo":
            cx, cy = sx, sy = R(pts[0][0]), R(pts[0][1]); out.append("M" + seq([cx, cy]))
        elif op in ("lineTo", "curveTo", "qCurveTo"):
            ps = [(R(x), R(y)) for x, y in pts]; out.append({"lineTo": "l", "curveTo": "c", "qCurveTo": "q"}[op] + seq([v for x, y in ps for v in (x - cx, y - cy)])); cx, cy = ps[-1]
        elif op in ("closePath", "endPath"):
            out.append("z"); cx, cy = sx, sy
    return "".join(out)

def android_vector(h_dp, color, wordmark=True, pad=0.0):
    """VectorDrawable XML: mark at height H=100 units (+ text), single brand color."""
    H = 100.0; s = H / MARK_BBOX[3]; mw = MARK_BBOX[2] * s
    td, end = text_d(H, mw + 0.30 * H, 10_000) if wordmark else ("", mw)
    W = end + 2 if wordmark else mw
    if pad:   # square canvas with the mark centred (splash icon / circle masks)
        side = H * (1 + pad); ox, oy = (side - mw) / 2, (side - H) / 2
        return (f'<vector xmlns:android="http://schemas.android.com/apk/res/android"\n    android:width="{h_dp}dp" android:height="{h_dp}dp"\n'
                f'    android:viewportWidth="{side:.1f}" android:viewportHeight="{side:.1f}">\n    <group android:translateX="{ox:.2f}" android:translateY="{oy:.2f}">\n'
                f'    <group android:scaleX="{s:.6f}" android:scaleY="{s:.6f}">\n      <group android:translateX="{1121 - MARK_BBOX[0]}" android:translateY="0">\n'
                f'        <path android:fillColor="{color}" android:pathData="{rel_d(mark_d())}"/>\n      </group>\n    </group>\n    </group>\n</vector>\n')
    tp = f'\n    <path android:fillColor="{color}" android:pathData="{rel_d(td, 0.1)}"/>' if wordmark else ""
    return (f'<vector xmlns:android="http://schemas.android.com/apk/res/android"\n    android:width="{h_dp * W / H:.1f}dp" android:height="{h_dp}dp"\n'
            f'    android:viewportWidth="{W:.1f}" android:viewportHeight="{H:.1f}">\n'
            f'    <group android:scaleX="{s:.6f}" android:scaleY="{s:.6f}">\n      <group android:translateX="{1121 - MARK_BBOX[0]}" android:translateY="0">\n'
            f'        <path android:fillColor="{color}" android:pathData="{rel_d(mark_d())}"/>\n      </group>\n    </group>{tp}\n</vector>\n')
