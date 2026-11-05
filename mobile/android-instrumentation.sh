#!/usr/bin/env bash
# Optional device instrumentation probe for Phase B #83.
# When adb + a device are present: install APK (if given), launch, dump package/activity.
# When no device: exit 0 with SKIP — never claims E2E pass.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
ART=${KOMBOE_ARTIFACTS:-/workspace/artifacts}
APK=${KOMBOE_ANDROID_APK:-"$ART/komboe-android-debug.apk"}
PKG=io.komboe.android

echo "android-instrumentation: apk=$APK"

fail() { echo "FAIL: $*" >&2; exit 1; }
ok() { echo "OK: $*"; }
skip() { echo "SKIP: $*"; }

[[ -f "$ROOT/mobile/ANDROID-E2E.md" ]] || fail "missing ANDROID-E2E.md"
[[ -f "$ROOT/mobile/android-e2e-check.sh" ]] || fail "missing android-e2e-check.sh"
ok "harness docs present"

if ! command -v adb >/dev/null 2>&1; then
  skip "adb not on PATH — no device instrumentation this run"
  echo "android-instrumentation: PASS (docs-only; device E2E NOT run)"
  exit 0
fi

mapfile -t DEVS < <(adb devices | awk 'NR>1 && $2=="device" {print $1}')
if [[ ${#DEVS[@]} -eq 0 ]]; then
  skip "no adb device/emulator in 'device' state"
  echo "android-instrumentation: PASS (docs-only; device E2E NOT run)"
  exit 0
fi
ok "adb device(s): ${DEVS[*]}"

if [[ -f "$APK" && -s "$APK" ]]; then
  adb install -r "$APK" >/tmp/komboe-adb-install.log 2>&1 || fail "adb install failed (see /tmp/komboe-adb-install.log)"
  ok "installed $APK"
else
  skip "APK missing at $APK — probing already-installed package only"
fi

if ! adb shell pm path "$PKG" 2>/dev/null | grep -q "package:"; then
  fail "package $PKG not installed on device"
fi
ok "package $PKG installed"

# Launch launcher activity (MainActivity name may vary by upstream; monkey is the fallback).
adb shell am start -n "$PKG/.MainActivity" >/tmp/komboe-adb-start.log 2>&1 \
  || adb shell monkey -p "$PKG" -c android.intent.category.LAUNCHER 1 >/tmp/komboe-adb-start.log 2>&1 \
  || fail "could not launch $PKG"
ok "launched $PKG"

# Dump top activity — evidence only; do not mark STATUS #83 done from this script alone.
adb shell dumpsys activity activities 2>/dev/null | rg -i "komboe|mResumedActivity|topResumedActivity" | head -20 \
  | tee /tmp/komboe-android-instrumentation-activity.txt >/dev/null || true
ok "wrote /tmp/komboe-android-instrumentation-activity.txt"

cat <<'NOTE'
android-instrumentation: device probe complete.
Still REQUIRED for STATUS #83 → done: manual checklist in mobile/ANDROID-E2E.md
(login, sync, autofill service, PIN, biometric). This script does not claim those.
NOTE
echo "android-instrumentation: PASS (launch probe only — full E2E NOT claimed)"
