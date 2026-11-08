#!/usr/bin/env python3
"""Downloads manifest: only real files are published, bytes match sha256, QR stays local."""
import hashlib
import json
import os
import shutil
import subprocess
import threading
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/build-downloads-manifest.py"
COMPONENT = ROOT / "clients/upstream/apps/web/src/app/tools/downloads/downloads.component.ts"
LAYOUT = ROOT / "clients/upstream/apps/web/src/app/layouts/user-layout.component.html"
ROUTING = ROOT / "clients/upstream/apps/web/src/app/oss-routing.module.ts"
MARKETING = ROOT / "apps/web-marketing/downloads.html"
DOCKERFILE = ROOT / "docker/Dockerfile.clients"


def run_manifest(artifacts: Path, publish: Path, outs: list[Path]) -> dict:
    cmd = ["python3", str(SCRIPT), "--artifacts", str(artifacts), "--publish-dir", str(publish), "--url-prefix", "downloads/"]
    for dest in outs:
        cmd.extend(["--out", str(dest)])
    subprocess.check_call(cmd)
    return json.loads(outs[0].read_text(encoding="utf-8"))


def serve(directory: Path):
    os.chdir(directory)
    server = ThreadingHTTPServer(("127.0.0.1", 0), SimpleHTTPRequestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def qr_roundtrip(url: str, dest: Path) -> None:
    import segno

    segno.make(url, error="m").save(dest, scale=4)
    decoded = subprocess.check_output(["zbarimg", "--quiet", "--raw", str(dest)], text=True).strip()
    assert decoded == url, (decoded, url)


def main() -> None:
    work = Path("/tmp/komboe-downloads-test")
    if work.exists():
        shutil.rmtree(work)
    artifacts = work / "artifacts"
    publish = work / "www/downloads"
    artifacts.mkdir(parents=True)
    payload = b"PK\x03\x04komboe-extension-fixture-not-a-store-build"
    (artifacts / "komboe-chrome-mv3.zip").write_bytes(payload)
    (artifacts / "komboe-android-debug.apk").write_bytes(b"debug-apk-must-not-ship")
    out = work / "komboe-downloads.json"
    manifest = run_manifest(artifacts, publish, [out])

    assert "komboe-android-debug.apk" in manifest["refused"]
    by_id = {asset["id"]: asset for asset in manifest["assets"]}
    ext = by_id["extension-chromium-mv3"]
    assert ext["status"] == "published"
    assert ext["sha256"] == hashlib.sha256(payload).hexdigest()
    assert ext["size"] == len(payload)
    assert ext["version"] == "2026.10.1"
    assert ext["url"] == "downloads/komboe-chrome-mv3.zip"
    assert ext["qr"] is True
    assert "unsigned" in ext["channel"]
    assert (publish / "komboe-chrome-mv3.zip").read_bytes() == payload

    android = by_id["android"]
    ios = by_id["ios"]
    macos = by_id["desktop-macos"]
    windows = by_id["desktop-windows"]
    assert android["status"] == "unavailable" and android["url"] is None and android["qr"] is False
    assert "debug" in android["reason"].lower()
    assert ios["status"] == "unavailable" and ios["qr"] is False and "QR" in ios["reason"]
    assert macos["status"] == "unavailable" and "signing" in macos["reason"].lower()
    assert windows["status"] == "unavailable"
    blob = json.dumps(manifest)
    for banned in ("play.google.com", "apps.apple.com", "chromewebstore", "nngceckbapebfimnlniiiahkandclblb", "komboe-android-debug.apk"):
        assert banned not in blob or banned == "komboe-android-debug.apk" and banned in manifest["refused"]

    server = serve(work / "www")
    try:
        base = f"http://127.0.0.1:{server.server_address[1]}/"
        downloaded = urllib.request.urlopen(base + ext["url"], timeout=10).read()
        assert downloaded == payload
        assert hashlib.sha256(downloaded).hexdigest() == ext["sha256"]
        absolute = base + ext["url"]
        qr_roundtrip(absolute, work / "qr.png")
    finally:
        server.shutdown()

    empty = work / "empty"
    empty.mkdir()
    empty_out = work / "empty.json"
    empty_manifest = run_manifest(empty, work / "empty-publish", [empty_out])
    assert all(asset["status"] == "unavailable" and asset["url"] is None and asset["qr"] is False for asset in empty_manifest["assets"])

    layout = LAYOUT.read_text(encoding="utf-8")
    routing = ROUTING.read_text(encoding="utf-8")
    component = COMPONENT.read_text(encoding="utf-8")
    assert layout.count('data-testid="nav-downloads"') == 2
    assert 'path: "downloads"' in routing
    assert 'path: "register"' in routing
    assert "app-vault-onboarding" not in (ROOT / "clients/upstream/apps/web/src/app/vault/individual-vault/vault.component.html").read_text(encoding="utf-8")
    assert "qrious.min.js" in component
    assert "qrserver" not in component and "chart.googleapis" not in component
    assert "komboe-android-debug" not in component
    marketing = MARKETING.read_text(encoding="utf-8")
    committed = json.loads((ROOT / "distribution/komboe-downloads.json").read_text(encoding="utf-8"))
    published_copy = json.loads((ROOT / "apps/web-marketing/komboe-downloads.json").read_text(encoding="utf-8"))
    assert published_copy == committed
    assert "downloads-manifest-empty" in marketing
    assert "coming soon" not in marketing.lower()
    assert "BROWSER-EXTENSIONS.md" in marketing
    for asset in committed["assets"]:
        assert f'marketing-download-{asset["id"]}' in marketing
        if asset["status"] != "published":
            assert asset["reason"] in marketing
            assert asset["qr"] is False
    docker = DOCKERFILE.read_text(encoding="utf-8")
    assert "build-downloads-manifest.py" in docker
    assert "komboe-chrome-mv3" in docker
    print("DOWNLOADS MANIFEST PASS", ext["sha256"])


if __name__ == "__main__":
    main()
