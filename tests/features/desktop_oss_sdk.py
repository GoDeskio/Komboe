"""Shipped desktop app uses the GPL sdk-internal only: no commercial SDK, no bitwarden_license code, Komboe repo metadata."""
import json, os, subprocess, sys, tempfile
ASAR = sys.argv[1] if len(sys.argv) > 1 else "/workspace/run/desk/squashfs-root/resources/app.asar"
TOOL = os.path.join(os.path.dirname(__file__), "../../clients/upstream/node_modules/.bin/asar")
files = subprocess.run([TOOL, "list", ASAR], capture_output=True, text=True, check=True).stdout.splitlines()
assert not [f for f in files if "commercial-sdk-internal" in f], "commercial SDK must not ship"
assert not [f for f in files if "bitwarden_license" in f], "bitwarden_license code must not ship"
assert any(f.startswith("/node_modules/@bitwarden/sdk-internal/") for f in files), "GPL sdk-internal must ship"
unpacked = ASAR + ".unpacked/node_modules/@bitwarden"
assert not os.path.exists(os.path.join(unpacked, "commercial-sdk-internal")), "commercial SDK in app.asar.unpacked"
with tempfile.TemporaryDirectory() as d:
    for f in ("package.json", "main.js", "index.html"):
        subprocess.run([TOOL, "extract-file", ASAR, f], cwd=d, check=True)
    pkg = json.load(open(os.path.join(d, "package.json")))
    assert "GoDeskio/Komboe" in pkg["repository"]["url"], pkg["repository"]
    for f in ("main.js", "index.html"):
        t = open(os.path.join(d, f), errors="ignore").read()
        assert "commercial-sdk-internal" not in t and "bitwarden_license" not in t, f
cfg = json.load(open(os.path.join(os.path.dirname(__file__), "../../clients/upstream/apps/desktop/electron-builder.json")))
assert any("commercial-sdk-internal" in p and p.startswith("!") for p in cfg["files"])
print("DESKTOP OSS SDK PASS")
