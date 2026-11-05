#!/usr/bin/env bash
# Phase B #83 — run all pre-device Android harness steps in order.
# Never claims device E2E. Safe on a box with no adb / no APK.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
echo "android-harness: starting (pre-device + optional adb probe)"
bash "$ROOT/mobile/android-e2e-check.sh"
bash "$ROOT/mobile/android-instrumentation.sh"
echo
echo "android-harness: PASS (static/docs + optional probe — device E2E NOT claimed)"
