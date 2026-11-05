# Phase B — local slice status (2026-11-05 Arizona MST)

Cheap local work on the box clone (`/workspace/Komboe`), **no CloudAgent** (on-demand spend capped). Branched from `main` @ `6a11c65a` (after #103/#104/#105).

## Inventory (PIN / biometric / Android / extensions)

| Area | Feature # | Code location | State after this slice |
|---|---|---|---|
| Desktop PIN | 52 | `apps/desktop` set-PIN dialog + `PinServiceAbstraction` via `DesktopLockComponentService.getAvailableUnlockOptions$` | Wired in UI; no further code gaps found after #105 without a live desktop session |
| Desktop biometrics | 52 | `apps/desktop/src/key-management/biometrics/*` (Win Hello / Touch ID / Linux polkit) | Native services present; lock screen toasts via `LockComponentService.getBiometricsError`. Live OS biometric still needs hardware |
| Android APK | 83 | `mobile/android-build.sh`, rebrand, `komboe-sdk` | APK build path exists; **device E2E not run** |
| Android E2E harness | 83 | `mobile/ANDROID-E2E.md`, `android-e2e-check.sh`, `android-instrumentation.sh`, `android-harness.sh` | Combined harness + biometric permission string check when APK present |
| Ext Chrome/Edge/Brave/Opera | 84 | Chromium MV3 zip | Done previously; Cerebro in matrix |
| Ext Firefox | 85 | Firefox zip | Done previously |
| Ext Safari | 86 | — | Still blocked (needs Mac) |
| Ext Vivaldi / Tor / Cerebro | 87 | `clients/SUPPORTED-BROWSERS.json` `load_contract`, `scripts/extension-smoke.mjs` | Matrix-driven load contracts for Cerebro/Vivaldi (MV3) and Tor (Firefox MV2); **UI E2E not run** |
| macOS / iOS / Safari | 82/83/86 | — | Skip on Linux box |

## What landed in this PR

1. `clients/SUPPORTED-BROWSERS.json` — `load_contract` on **Cerebro**, **Vivaldi**, and **Tor** (source of truth for smoke).
2. `scripts/extension-smoke.mjs` — asserts each declared `load_contract` against in-repo manifests (no hardcoded Cerebro-only path).
3. `docs/BROWSER-EXTENSIONS.md` — Vivaldi + Tor load-contract sections.
4. `mobile/android-harness.sh` — runs e2e-check then instrumentation; never claims device E2E.
5. `mobile/android-e2e-check.sh` — when APK present, looks for `USE_BIOMETRIC` / `USE_FINGERPRINT` packaging signals.
6. `docs/STATUS.md` — removed duplicate #81–#84 rows; honest #52/#83/#87 evidence.
7. `tests/features/phase_b.py` — asserts Tor/Vivaldi load_contracts + `android-harness.sh`.

## Still needs device / Mac / spend

- Real biometric prompt on Windows Hello / Touch ID / polkit (hardware).
- Android emulator or phone for login + PIN + biometric + autofill E2E.
- Manual load of MV3 zip in Vivaldi and Cerebro; Firefox zip in Tor Browser.
- Safari / iOS / macOS desktop (Mac).
- Heavy Phase B client rebuilds via CloudAgent (capped).

Without those, further local Phase B code is mostly busywork — do not invent it.

## Commands

```sh
node scripts/extension-smoke.mjs
bash mobile/android-harness.sh
```

Do **not** treat either command as device / browser-UI E2E.

## Remotes

- GitHub: `GoDeskio/Komboe`
- GitGoat mirror: `Godeskadmin/Komboe` is a GitHub **pull-mirror**. After GitHub push, `POST /api/v1/repos/Godeskadmin/Komboe/mirror-sync` with `GITGOAT_GODESKADMIN_REPO_WRITE_TOKEN` from `/home/box/.secrets/gitgoat-godeskadmin-repo-write.env` (or wait ≤15m). Do **not** recreate `GoDeskio/Komboe` on GitGoat; direct `git push` to the mirror is read-only.
- Drafts #90 / #97 untouched. No Coolify / DNS / deploy.
