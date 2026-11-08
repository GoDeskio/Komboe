#!/usr/bin/env python3
"""Build komboe-downloads.json from files that actually exist in an artifact directory.

The clients image runs this after it builds komboe-chrome-mv3.zip and copies that
zip into the web vault. A checkout with an empty artifact directory publishes no
installers. GitHub Releases are not assumed to contain assets.

Refused on purpose:
- komboe-android-debug.apk (internal debug build, not a production release)
- any URL that is not produced from a file in the artifact directory
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXTENSION_DOCS = "https://github.com/GoDeskio/Komboe/blob/main/docs/BROWSER-EXTENSIONS.md"
SOURCE = "https://github.com/GoDeskio/Komboe"

# filename None means there is no artifact name because the platform is not built.
CATALOG = [
    {
        "id": "extension-chromium-mv3",
        "filename": "komboe-chrome-mv3.zip",
        "name": "Browser extension (Chromium)",
        "platforms": ["Chrome", "Edge", "Brave", "Opera", "Vivaldi", "Cerebro"],
        "kind": "extension",
        "channel": "unsigned-testing",
        "docsUrl": EXTENSION_DOCS,
        "install": (
            "No extension store listing. Unzip the file and load it unpacked "
            "(chrome://extensions, edge://extensions, or the Chromium equivalent). "
            "The same zip is what Edge, Brave, Opera, Vivaldi, and Cerebro load."
        ),
        "missing": "The clients image has not published komboe-chrome-mv3.zip into this vault.",
    },
    {
        "id": "extension-firefox",
        "filename": "komboe-firefox.zip",
        "name": "Browser extension (Firefox)",
        "platforms": ["Firefox", "Tor Browser"],
        "kind": "extension",
        "channel": "unsigned-testing",
        "docsUrl": EXTENSION_DOCS,
        "install": "No add-ons listing. Load the zip as a temporary add-on from about:debugging.",
        "missing": "No komboe-firefox.zip is in the release artifacts.",
    },
    {
        "id": "desktop-windows",
        "filename": "komboe-desktop-win-x64-setup.exe",
        "name": "Desktop for Windows",
        "platforms": ["Windows"],
        "kind": "desktop",
        "channel": "unsigned-testing",
        "docsUrl": SOURCE,
        "install": "Unsigned testing installer. Windows SmartScreen will warn.",
        "missing": "No verified current Windows installer. Older unsigned builds are not offered.",
    },
    {
        "id": "desktop-linux-deb",
        "filename": "komboe-desktop-amd64.deb",
        "name": "Desktop for Linux (.deb)",
        "platforms": ["Linux"],
        "kind": "desktop",
        "channel": "unsigned-testing",
        "docsUrl": SOURCE,
        "install": "Unsigned testing package.",
        "missing": "No verified current Linux .deb. Older unsigned builds are not offered.",
    },
    {
        "id": "desktop-linux-appimage",
        "filename": "komboe-desktop-x86_64.AppImage",
        "name": "Desktop for Linux (AppImage)",
        "platforms": ["Linux"],
        "kind": "desktop",
        "channel": "unsigned-testing",
        "docsUrl": SOURCE,
        "install": "Unsigned testing AppImage.",
        "missing": "No verified current Linux AppImage. Older unsigned builds are not offered.",
    },
    {
        "id": "desktop-macos",
        "filename": "komboe-desktop-macos.dmg",
        "name": "Desktop for macOS",
        "platforms": ["macOS"],
        "kind": "desktop",
        "channel": "unavailable",
        "docsUrl": SOURCE,
        "install": "",
        "missing": "No macOS build. Apple signing and notarization are not set up.",
    },
    {
        "id": "android",
        "filename": "komboe-android.apk",
        "name": "Android",
        "platforms": ["Android"],
        "kind": "mobile",
        "channel": "unavailable",
        "docsUrl": "https://github.com/GoDeskio/Komboe/tree/main/mobile",
        "install": "",
        "missing": (
            "No production Android APK. An internal debug APK exists on a build machine "
            "and is not published: device login, autofill, PIN, and biometric are unverified."
        ),
    },
    {
        "id": "ios",
        "filename": None,
        "name": "iPhone and iPad",
        "platforms": ["iOS"],
        "kind": "mobile",
        "channel": "unavailable",
        "docsUrl": SOURCE,
        "install": "",
        "missing": "No iOS build, App Store listing, or TestFlight. There is no QR code.",
    },
]

REFUSED = {"komboe-android-debug.apk"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def version_from(path: Path | None) -> str | None:
    if path is None or not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    value = data.get("version")
    return value if isinstance(value, str) and value else None


def build(artifacts: Path, version_file: Path | None, url_prefix: str, publish_dir: Path | None) -> dict:
    refused = sorted(name for name in REFUSED if (artifacts / name).is_file())
    assets = []
    for item in CATALOG:
        filename = item["filename"]
        source = artifacts / filename if filename else None
        published = source is not None and source.is_file()
        asset = {
            "id": item["id"],
            "name": item["name"],
            "platforms": item["platforms"],
            "kind": item["kind"],
            "filename": filename,
            "version": version_from(version_file) if published else None,
            "status": "published" if published else "unavailable",
            "channel": item["channel"] if not published or item["channel"] != "unavailable" else "unsigned-testing",
            "sha256": sha256(source) if published else None,
            "size": source.stat().st_size if published else None,
            "url": None,
            "docsUrl": item["docsUrl"],
            "install": item["install"],
            "reason": None if published else item["missing"],
            "qr": False,
        }
        if published and publish_dir is not None:
            publish_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, publish_dir / filename)
            asset["url"] = f"{url_prefix}{filename}"
            asset["qr"] = True
            if item["channel"] == "unavailable":
                asset["channel"] = "unsigned-testing"
        elif published:
            asset["reason"] = "File is present but no publish directory was set, so it is not downloadable."
            asset["status"] = "unavailable"
            asset["sha256"] = None
            asset["size"] = None
            asset["version"] = None
        assets.append(asset)
    return {
        "schema": 1,
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "generator": "scripts/build-downloads-manifest.py",
        "note": (
            "A download URL is present only when the named file was in the artifact directory "
            "and copied to the publish directory. Store listings are not used. "
            "komboe-android-debug.apk is refused."
        ),
        "refused": refused,
        "assets": assets,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--version-file", type=Path, default=ROOT / "clients/upstream/apps/browser/src/manifest.v3.json")
    parser.add_argument("--out", type=Path, action="append", required=True)
    parser.add_argument("--publish-dir", type=Path)
    parser.add_argument("--url-prefix", default="downloads/")
    args = parser.parse_args()
    if not args.artifacts.is_dir():
        raise SystemExit(f"artifact directory does not exist: {args.artifacts}")
    manifest = build(args.artifacts, args.version_file, args.url_prefix, args.publish_dir)
    text = json.dumps(manifest, indent=2) + "\n"
    for dest in args.out:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8")
        print(f"wrote {dest}")


if __name__ == "__main__":
    main()
