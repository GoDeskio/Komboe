"""Store/package metadata is Komboe-branded; Bitwarden appears only as attribution."""
import glob, os, re, xml.dom.minidom
R = os.path.join(os.path.dirname(__file__), "../../clients/upstream/apps")
ATTR = re.compile(r"based on Vaultwarden and Bitwarden clients|not affiliated with or endorsed by Bitwarden Inc\.|Portions © Bitwarden Inc\.")
files = (glob.glob(R + "/cli/stores/**/*", recursive=True) + glob.glob(R + "/desktop/stores/chocolatey/**/*", recursive=True)
         + glob.glob(R + "/browser/store/**/*", recursive=True))
for f in files:
    if not os.path.isfile(f) or f.endswith((".png", ".jpg")):
        continue
    t = ATTR.sub("", open(f, encoding="utf-8", errors="ignore").read())
    assert "bitwarden" not in t.lower(), f
    if f.endswith((".nuspec", ".xml", ".resx")):
        xml.dom.minidom.parseString(open(f, "rb").read())
assert {os.path.basename(d) for d in glob.glob(R + "/browser/store/locales/*")} == {"en", "en_GB", "en_IN"}
snap = open(R + "/cli/stores/snap/snapcraft.yaml").read()
assert snap.startswith("name: komboe\n") and "command: komboe" in snap and not re.search(r"\bbw\b", snap)
assert os.path.exists(R + "/cli/stores/chocolatey/komboe-cli.nuspec") and os.path.exists(R + "/desktop/stores/chocolatey/komboe.nuspec")
assert "GoDeskio/Komboe/releases" in open(R + "/desktop/stores/chocolatey/tools/chocolateyinstall.ps1").read()
for wf, n in (("build-cli.yml", "komboe-cli.nuspec"), ("build-desktop.yml", "komboe.nuspec")):
    assert n in open(R + "/../.github/workflows/" + wf).read()
print("PACKAGING META PASS")
