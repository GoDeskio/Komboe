#!/usr/bin/env python3
"""Komboe Android rebrand (idempotent): applicationId io.komboe.android, app name Komboe, padlock-K launcher.
Kotlin namespace/package names stay upstream (internal identifiers); copyright/license text untouched.
GPL-3.0: the upstream LICENSE.txt and a corresponding-source notice are copied into the APK assets."""
import glob, os, re, shutil, sys
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
    # Phase E: in-app logos must stay VectorDrawables (screens load them with rememberVectorPainter): wordmark / mark as vector paths.
    import sys; sys.path.insert(0, f"{ROOT}/branding/wordmark"); from wordmark_lib import android_vector
    for n, wm, hdp, pad in [("logo_bitwarden", True, 34, 0), ("logo_shield_icon", False, 288, 1.0), ("logo_bitwarden_icon", False, 48, 0)]:
        xml = f"{S}/ui/src/main/res/drawable/{n}.xml"; png_ = f"{S}/ui/src/main/res/drawable-nodpi/{n}.png"
        if os.path.exists(png_): os.remove(png_)
        new = android_vector(hdp, "#6D4AFF", wordmark=wm, pad=pad)
        if not os.path.exists(xml) or open(xml).read() != new: open(xml, "w").write(new); print("rebrand vector", os.path.relpath(xml, S))
    for p in glob.glob(f"{S}/app/src/*/res/values/ic_launcher_background.xml"):
        rw(p, lambda t: re.sub(r"(<color name=\"ic_launcher_background\">)[^<]*<", r"\1#FFFFFF<", t))
except ImportError: pass

# GPL-3.0 §4–§6: the binary must carry the license text and say where the source is.
assets = os.path.join(S, "app", "src", "main", "assets")
os.makedirs(assets, exist_ok=True)
upstream_license = os.path.join(S, "LICENSE.txt")
if not os.path.isfile(upstream_license):
    sys.exit("Bitwarden Android LICENSE.txt is missing; refusing to build without the GPL text")
license_head = open(upstream_license, encoding="utf-8").read(80)
if "GNU GENERAL PUBLIC LICENSE" not in license_head:
    sys.exit("Upstream LICENSE.txt is not the GNU GPL text")
shutil.copyfile(upstream_license, os.path.join(assets, "LICENSE.txt"))
shutil.copyfile(os.path.join(ROOT, "mobile", "ANDROID-SOURCE.txt"), os.path.join(assets, "komboe-source.txt"))
shutil.copyfile(os.path.join(ROOT, "THIRD-PARTY-NOTICES.md"), os.path.join(assets, "THIRD-PARTY-NOTICES.md"))
print("rebrand gpl assets", "LICENSE.txt", "komboe-source.txt", "THIRD-PARTY-NOTICES.md")

def patch(path, old, new, label):
    file = os.path.join(S, path)
    text = open(file, encoding="utf-8").read()
    if old not in text:
        if new in text:
            return
        sys.exit(f"gpl sdk wire: pattern missing in {path} ({label})")
    open(file, "w", encoding="utf-8").write(text.replace(old, new))
    print("gpl sdk", label)

sdk_dir = os.path.join(ROOT, "mobile", "komboe-sdk")
settings_path = os.path.join(S, "settings.gradle.kts")
settings = open(settings_path, encoding="utf-8").read()
if ":komboe-sdk" not in settings:
    open(settings_path, "a", encoding="utf-8").write(
        '\ninclude(":komboe-sdk")\nproject(":komboe-sdk").projectDir = file("%s")\n' % sdk_dir
    )
    print("gpl sdk", "settings")
patch("build.gradle.kts", "lockMode.set(LockMode.STRICT)", "lockMode.set(LockMode.LENIENT)", "lock lenient")
patch("app/build.gradle.kts", "    implementation(libs.bitwarden.sdk)\n", '    implementation(project(":komboe-sdk"))\n', "app dependency")
patch("authenticator/build.gradle.kts", "    implementation(libs.bitwarden.sdk)\n", '    implementation(project(":komboe-sdk"))\n', "authenticator dependency")
sdk_maven = '''        maven {
            name = "GitHubPackages (Bitwarden)"
            url = uri("https://maven.pkg.github.com/bitwarden/sdk")
            credentials {
                username = ""
                password = userProperties["gitHubToken"] as String? ?: System.getenv("GITHUB_TOKEN")
            }
        }
'''
patch("settings.gradle.kts", sdk_maven, "", "drop sdk maven repo")
patch(
    "app/src/main/kotlin/com/x8bit/bitwarden/data/platform/manager/SdkClientManagerImpl.kt",
    '''        if (!isBuildVersionAtLeast(Build.VERSION_CODES.S)) {
            nativeLibraryManager.loadLibrary("bitwarden_uniffi")
        }
''',
    "        // Komboe vault crypto is pure JVM code. There is no bitwarden_uniffi library to load.\n",
    "skip native sdk",
)
