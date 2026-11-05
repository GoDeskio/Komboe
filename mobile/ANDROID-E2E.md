# Android E2E harness (Phase B #83)

Komboe Android is built as `io.komboe.android` (fdroid debug) via `mobile/android-build.sh`.  
**This document does not claim a device/emulator run happened.** It records the harness and the exact steps to run when a device is available.

Updated 2026-11-05 Arizona MST.

## What exists today

| Piece | Path | Notes |
|---|---|---|
| Upstream pin | `mobile/ANDROID_UPSTREAM_PIN` | `v2026.10.1-bwpm` |
| Build | `mobile/android-build.sh` | Produces fdroid debug APK |
| Rebrand | `mobile/android_rebrand.py` | Komboe label, padlock-K assets, GPL assets |
| GPL SDK surface | `mobile/komboe-sdk` | Replaces `com.bitwarden:sdk-android` |
| Artifact check (no device) | `tests/features/phase_b.py` `#83` | Zip/manifest/badging only |
| Pre-device smoke | `mobile/android-e2e-check.sh` | APK presence, package id, label, GPL assets, biometric permission strings when APK present |
| Combined harness | `mobile/android-harness.sh` | Runs e2e-check then instrumentation; never claims device E2E |
| Device launch probe | `mobile/android-instrumentation.sh` | Optional adb install/launch; SKIP without device |

PIN / biometric unlock live in the upstream Android tree after clone+rebrand; they need a real device or emulator with a screen lock enrolled. iOS remains blocked without macOS.

## Pre-device check (safe on the build box)

```sh
# Prefer the combined harness (static + optional adb probe):
bash mobile/android-harness.sh
# or individually:
bash mobile/android-e2e-check.sh
bash mobile/android-instrumentation.sh
# optional:
KOMBOE_ARTIFACTS=/workspace/artifacts bash mobile/android-harness.sh
```

Exit 0 means docs/scripts (and the APK when present) look installable. When an APK is present, `android-e2e-check.sh` also looks for `USE_BIOMETRIC` / `USE_FINGERPRINT` permission strings in the binary manifest (packaging signal only). It does **not** mean login/autofill/PIN/biometric E2E passed.

## Device / emulator runbook (when hardware is available)

Prerequisites: Android SDK platform-tools (`adb`), an emulator AVD or a physical device with USB debugging, and the debug APK from `mobile/android-build.sh`.

```sh
# 1. Build (if needed)
bash mobile/android-build.sh
APK=${KOMBOE_ARTIFACTS:-/workspace/artifacts}/komboe-android-debug.apk
# or from the gradle output path printed by android-build.sh

# 2. Install
adb devices
adb install -r "$APK"

# 3. Launch
adb shell am start -n io.komboe.android/.MainActivity || \
  adb shell monkey -p io.komboe.android -c android.intent.category.LAUNCHER 1

# 4. Manual E2E checklist (record pass/fail; do not mark STATUS #83 done until these pass)
#    [ ] App label shows Komboe; splash uses padlock-K
#    [ ] Self-host server URL can be set
#    [ ] Register or log in against a local/test vault
#    [ ] Sync shows vault items
#    [ ] Autofill service can be enabled in Android settings
#    [ ] PIN unlock: set PIN in settings, lock vault, unlock with PIN
#    [ ] Biometric unlock: enroll device biometrics, enable in Komboe, lock, unlock
#    [ ] No Bitwarden Inc. user-facing branding in chrome/settings

# 5. Capture evidence
adb exec-out screencap -p > /tmp/komboe-android-e2e.png
adb logcat -d | rg -i 'komboe|AndroidRuntime' | tail -200 > /tmp/komboe-android-e2e.log
```

## Instrumentation hooks

### Pre-device (always safe)

```sh
bash mobile/android-e2e-check.sh
```

### Device launch probe (optional)

When `adb` sees a device/emulator:

```sh
bash mobile/android-instrumentation.sh
# optional:
KOMBOE_ANDROID_APK=/path/to/komboe-android-debug.apk bash mobile/android-instrumentation.sh
```

This installs (if APK present), launches `io.komboe.android`, and dumps the resumed activity. It does **not** mark STATUS #83 done.

### Future Espresso / Compose UI tests

When we add Espresso / Compose UI tests against the rebranded tree, keep them under the cloned android sources after rebrand (not committed upstream clones). Prefer:

- Package id assertions: `io.komboe.android`
- Login → vault list smoke against `KOMBOE_TLS_URL`
- Explicit `@Ignore("needs device biometrics")` on biometric cases so CI stays honest

Until those tests land, `android-e2e-check.sh` + `android-instrumentation.sh` + this checklist are the harness.
