# Phase B — local slice status (2026-11-05 Arizona MST)

Cheap local work on the box clone (`/workspace/Komboe`), **no CloudAgent** (on-demand spend capped). Branched from `main` @ `70787648`.

## Inventory (PIN / biometric / Android / extensions)

| Area | Feature # | Code location | State after this slice |
|---|---|---|---|
| Desktop PIN | 52 | `apps/desktop` set-PIN dialog + `PinServiceAbstraction` via `DesktopLockComponentService.getAvailableUnlockOptions$` | Wired in UI; needs live desktop session to E2E |
| Desktop biometrics | 52 | `apps/desktop/src/key-management/biometrics/*` (Win Hello / Touch ID / Linux polkit) | Native services present; lock screen now **toasts** on non-cancel failure (`couldNotCompleteBiometrics`); `getBiometricsError` maps polkit/Hello/TouchID strings |
| Android APK | 83 | `mobile/android-build.sh`, rebrand, `komboe-sdk` | APK build path exists; **device E2E not run** |
| Android E2E harness | 83 | `mobile/ANDROID-E2E.md`, `mobile/android-e2e-check.sh` | **New** — static APK checks + device runbook |
| Ext Chrome/Edge/Brave/Opera | 84 | Chromium MV3 zip | Done previously; Cerebro added to matrix |
| Ext Firefox | 85 | Firefox zip | Done previously |
| Ext Safari | 86 | — | Still blocked (needs Mac) |
| Ext Vivaldi / Tor / Cerebro | 87 | `clients/SUPPORTED-BROWSERS.json`, `docs/BROWSER-EXTENSIONS.md`, `scripts/extension-smoke.mjs` | Matrix + headless smoke; **UI E2E not run** in Vivaldi/Tor/Cerebro |
| macOS / iOS / Safari | 82/83/86 | — | Skip on Linux box |

## What landed in this PR

1. `clients/SUPPORTED-BROWSERS.json` — includes **Cerebro Browser** (Chromium MV3), Vivaldi, Tor.
2. `scripts/extension-smoke.mjs` — validates matrix + source manifests (+ artifact zips when present).
3. `docs/BROWSER-EXTENSIONS.md` — load checklists for Chromium family (incl. Cerebro) and Firefox/Tor.
4. README / FEATURES / STATUS updates for Cerebro + honest partials.
5. Desktop biometric unlock: toast on failure; richer `getBiometricsError` mapping + unit expectations.
6. Android E2E harness docs + `android-e2e-check.sh`.
7. `tests/features/phase_b.py` asserts the browser matrix (incl. Cerebro) for #84/#87 and harness files for #83.

## Still needs device / Mac / spend

- Real biometric prompt on Windows Hello / Touch ID / polkit (hardware).
- Android emulator or phone for login + PIN + biometric + autofill E2E.
- Manual load of MV3 zip in Vivaldi and Cerebro; Firefox zip in Tor Browser.
- Safari / iOS / macOS desktop (Mac).
- Heavy Phase B client rebuilds via CloudAgent (capped).

## Commands

```sh
node scripts/extension-smoke.mjs
bash mobile/android-e2e-check.sh
```

Do **not** treat either command as device E2E.
