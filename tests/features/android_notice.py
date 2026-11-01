#!/usr/bin/env python3
"""GPL-3.0 attribution for Bitwarden Android is recorded and would be packed into the APK."""
import os
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
PIN = (ROOT / "mobile/ANDROID_UPSTREAM_PIN").read_text().strip()
SOURCE = (ROOT / "mobile/ANDROID-SOURCE.txt").read_text()
NOTICES = (ROOT / "THIRD-PARTY-NOTICES.md").read_text()
NOTICE = (ROOT / "NOTICE").read_text()
UPSTREAM = (ROOT / "docs/UPSTREAM.md").read_text()
REBRAND = (ROOT / "mobile/android_rebrand.py").read_text()
BUILD = (ROOT / "mobile/android-build.sh").read_text()
COMMIT = "1470154cf3d3d0511cdbe5bfc6493971b6478edf"

assert PIN == "v2026.10.1-bwpm", PIN
for text, name in (
    (SOURCE, "ANDROID-SOURCE.txt"),
    (NOTICES, "THIRD-PARTY-NOTICES.md"),
    (NOTICE, "NOTICE"),
    (UPSTREAM, "UPSTREAM.md"),
):
    assert "v2026.10.1-bwpm" in text, name
    assert COMMIT in text, name
    assert "GPL-3.0" in text, name
    assert "bitwarden/android" in text, name

assert "GNU General Public License" in SOURCE
assert "komboe-source.txt" in SOURCE or "LICENSE.txt" in SOURCE
assert "com.bitwarden:sdk-android" in NOTICES
assert "Bitwarden Software Development Kit License Agreement" in NOTICES
assert "shutil.copyfile" in REBRAND and 'assets, "LICENSE.txt"' in REBRAND
assert "GNU GENERAL PUBLIC LICENSE" in BUILD
assert "v2026.10.1-bwpm" in BUILD
print("ANDROID NOTICE PASS")
