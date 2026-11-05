#!/usr/bin/env bash
# Pre-device Android smoke for Phase B #83.
# Validates the debug APK artifact when present. Never claims a device E2E run.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
ART=${KOMBOE_ARTIFACTS:-/workspace/artifacts}
APK=${KOMBOE_ANDROID_APK:-"$ART/komboe-android-debug.apk"}
PIN=$(cat "$ROOT/mobile/ANDROID_UPSTREAM_PIN")

echo "android-e2e-check: pin=$PIN"
echo "android-e2e-check: apk=$APK"

fail() { echo "FAIL: $*" >&2; exit 1; }
ok() { echo "OK: $*"; }

[[ -f "$ROOT/mobile/ANDROID-SOURCE.txt" ]] || fail "missing mobile/ANDROID-SOURCE.txt"
[[ -f "$ROOT/mobile/android-build.sh" ]] || fail "missing mobile/android-build.sh"
[[ -f "$ROOT/mobile/ANDROID-E2E.md" ]] || fail "missing mobile/ANDROID-E2E.md"
grep -q "io.komboe.android" "$ROOT/mobile/ANDROID-E2E.md" || fail "ANDROID-E2E.md missing package id"
ok "harness docs + build scripts present"

if [[ ! -f "$APK" ]] || [[ ! -s "$APK" ]]; then
  echo "SKIP: APK not present at $APK (build with mobile/android-build.sh). Harness docs OK."
  echo "android-e2e-check: PASS (docs-only; no device E2E claimed)"
  exit 0
fi

python3 - "$APK" <<'PY'
import sys, zipfile
apk = sys.argv[1]
z = zipfile.ZipFile(apk)
man = z.read("AndroidManifest.xml")
# binary XML still embeds UTF-16-LE package strings in AAPT-produced manifests
pkg = "io.komboe.android".encode("utf-16-le")
if pkg not in man:
    # some builds may store ASCII; accept either
    if b"io.komboe.android" not in man:
        raise SystemExit("package id io.komboe.android not found in AndroidManifest.xml")
print("OK: package id present in AndroidManifest.xml")
names = set(z.namelist())
for n in ("logo_bitwarden", "logo_shield_icon", "logo_bitwarden_icon"):
    path = f"res/drawable/{n}.xml"
    if path not in names:
        raise SystemExit(f"missing VectorDrawable {path}")
print("OK: in-app VectorDrawables present")
# GPL assets when packed into the APK assets/
for f in ("LICENSE.txt", "komboe-source.txt"):
    hits = [n for n in names if n.endswith(f) or n.endswith("assets/" + f)]
    if not hits:
        print(f"WARN: {f} not found inside APK (expected under assets/ for GPL offer)")
    else:
        print(f"OK: found {hits[0]}")
# Biometric / fingerprint permission strings (UTF-16-LE in binary XML, or ASCII).
# Presence is a packaging signal only — not a device E2E claim.
bio_needles = (
    "android.permission.USE_BIOMETRIC",
    "android.permission.USE_FINGERPRINT",
)
found_bio = []
for perm in bio_needles:
    if perm.encode("utf-16-le") in man or perm.encode("ascii") in man:
        found_bio.append(perm)
if found_bio:
    print("OK: biometric-related permission(s) in manifest: " + ", ".join(found_bio))
else:
    print("WARN: USE_BIOMETRIC / USE_FINGERPRINT not found in AndroidManifest.xml "
          "(upstream may declare them in a merged flavor manifest — check device build)")
PY

if command -v aapt2 >/dev/null 2>&1; then
  AAPT2=$(command -v aapt2)
elif [[ -d /workspace/tools/android-sdk/build-tools ]]; then
  AAPT2=$(ls -d /workspace/tools/android-sdk/build-tools/*/aapt2 2>/dev/null | sort | tail -1 || true)
else
  AAPT2=
fi
if [[ -n "${AAPT2:-}" && -x "$AAPT2" ]]; then
  badge=$("$AAPT2" dump badging "$APK")
  echo "$badge" | grep -q "application-label:'Komboe'" || fail "application-label is not Komboe"
  echo "$badge" | grep -q "name='io.komboe.android'" || fail "badging package name mismatch"
  ok "aapt2 badging: label Komboe, package io.komboe.android"
else
  echo "SKIP: aapt2 not available for badging"
fi

echo
echo "android-e2e-check: PASS (APK static checks only — device E2E NOT run)"
