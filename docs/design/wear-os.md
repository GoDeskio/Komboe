# Design: Wear OS companion

Status: scaffold. Full Play Store build needs Android SDK wear images and store credentials (Dustin go for store submit).

## Scope
- Read-only unlock codes / TOTP display after phone confirms biometric.
- No vault ciphertext stored on the watch beyond short-lived OTP secrets the user opts into.
- Phone app remains source of truth; watch is a companion.

See `clients/wearos/README.md`.
