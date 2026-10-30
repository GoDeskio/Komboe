# Running Komboe locally (native build, no Docker)

Tested on Linux x86_64. Development/testing only - not a production deployment guide.

## Server (Vaultwarden 1.37.4 based)
```sh
cd server/upstream
OPENSSL_LIB_DIR=/usr/lib/x86_64-linux-gnu OPENSSL_INCLUDE_DIR=/usr/include \
  cargo build --release --features sqlite      # Rust >= 1.89; ~18 min cold
```

## Web vault (clients web-v2026.10.1, OSS build only)
```sh
cd clients/upstream            # bitwarden_license/ is never imported
npm ci --ignore-scripts        # Node >= 24.17
cd apps/web && NODE_OPTIONS=--max-old-space-size=9000 npm run dist:oss:selfhost
```
Webpack peaks at ~7 GB RSS; add swap on small machines.

## Run
```sh
export DATA_FOLDER=$PWD/data ROCKET_ADDRESS=127.0.0.1 ROCKET_PORT=8000 SIGNUPS_ALLOWED=true \
  ORG_EVENTS_ENABLED=true ORG_GROUPS_ENABLED=true WEB_VAULT_ENABLED=true \
  WEB_VAULT_FOLDER=$PWD/clients/upstream/apps/web/build ADMIN_TOKEN=<choose-a-local-value>
server/upstream/target/release/vaultwarden
```
For the test suites, also relax rate limits (`LOGIN_RATELIMIT_SECONDS=1 LOGIN_RATELIMIT_MAX_BURST=10000`,
same for `ADMIN_` and `UNAUTHENTICATED_`).

## Tests
```sh
python3 tests/e2e/roundtrip.py                       # register/login/create/sync + DB holds only ciphertext
KOMBOE_DB=data/db.sqlite3 KOMBOE_ADMIN_TOKEN=... python3 tests/features/run.py --write-status docs/STATUS.md
bash scripts/check-licenses.sh
```

## HTTPS instance (needed by web vault E2E and CLI)
Clients refuse plain-HTTP servers. Run a second instance on the same `DATA_FOLDER` with a local self-signed cert:
```sh
ROCKET_PORT=8443 ROCKET_TLS='{certs="tls/cert.pem",key="tls/key.pem"}' DOMAIN=https://localhost:8443 server/upstream/target/release/vaultwarden
```
Family console (admin seats/members/split-off approval, no vault read): `https://localhost:8443/api/komboe/family-console`.

## Playwright E2E
```sh
bash tests/playwright/run.sh   # fresh fixtures, then node e2e.mjs -> tests/playwright/results.json
```
Env: `KOMBOE_ADMIN_TOKEN` (server admin token) and `KOMBOE_EXT_DIR` (unpacked `komboe-chrome-mv3.zip`). Currently 17/17
steps pass: web vault login/items/sharing, the vault health reports (weak, reused, unsecured, inactive 2FA, exposed), an
encrypted export that the test decrypts on its own, and the browser extension: it loads, logs in through the
"Choose your Komboe server" -> self-hosted picker (no Bitwarden cloud regions offered), and autofills from the inline menu.

## CLI (local testing only)
```sh
export NODE_EXTRA_CA_CERTS=tls/cert.pem
komboe config server https://localhost:8443
komboe login you@example.test --passwordenv KPW --raw   # prints session
komboe list items --session <session>
```
Build: `NODE_ENV=production npx webpack` in `apps/cli`, then `npx pkg . --targets node22-linux-x64 --output komboe-linux-x64`.

**Migration note (CLI rename):** the command is now `komboe` (was `bw`) and its data dir is `Komboe CLI`
(`~/.config/Komboe CLI`, `%APPDATA%\Komboe CLI`, `~/Library/Application Support/Komboe CLI`). Existing upstream
CLI users can move their old `Bitwarden CLI` dir to the new name, or set `BITWARDENCLI_APPDATA_DIR` to keep using it.
The env var names (`BITWARDENCLI_*`, `BW_SESSION`) are unchanged for script compatibility.

## Desktop (Electron, Linux)
apt is broken on this box, so native deps (pkg-config, dbus, libsecret, glib) come from a micromamba env:
```sh
bash desktop/desktop-build.sh   # desktop_native (Rust) -> npm run build -> electron-builder AppImage + deb
```
Outputs `Komboe-<ver>-x86_64.AppImage` and a `.deb`; the app id is `io.komboe.desktop` and the executable is `komboe`. Launch it with
`./komboe --no-sandbox` (no user namespaces here). Smoke check: it launches on X11. The current artifacts predate two fixes in rebrand step 7,
the window title (`<title>Komboe</title>`) and the deb package name (`komboe`), so rebuild to pick them up (needs ~3 GB free disk).
`tests/playwright/desktop.mjs` launches the unpacked app with `--remote-debugging-port` and attaches with `chromium.connectOverCDP` (the release fuses block `--inspect`, but CDP works). Set `KOMBOE_DESKTOP=apps/desktop/dist/linux-unpacked`; `tests/playwright/run.sh` runs it after the web/extension suite. Known gap: the X11 WM_CLASS is still `bitwarden` (it comes from the upstream package name).

## Not buildable on this box
- Windows desktop: NSIS needs wine, and even the portable `zip` target needs the Windows build of the native Rust module (`desktop_napi`), which needs mingw-w64 or MSVC. Neither is on this box, so a zip would not run. Build on a Windows CI runner.
- iOS, Safari and macOS desktop: need macOS.

## Android debug APK (no apt needed)
Portable toolchain in `/workspace/tools`: Temurin JDK 21 (upstream `jvmTarget = 21`; JDK 17 is also there but too old) and
Android commandline-tools. `GITHUB_TOKEN` (any token with `read:packages`) is needed because upstream pulls
`com.bitwarden:sdk-android` from GitHub Packages.
```sh
GITHUB_TOKEN=... bash mobile/android-build.sh   # pin: mobile/ANDROID_UPSTREAM_PIN, rebrand: mobile/android_rebrand.py
```
Output: `io.komboe.android-fdroid.apk` (fdroid flavor, no Google Play services/Firebase), package id `io.komboe.android`.

### Android icons
`mobile/android_rebrand.py` swaps the launcher foreground, monochrome and in-app logo vectors for padlock-K PNGs in `drawable-nodpi` (adaptive icons override the mipmaps on API 26+). The build needs `GITHUB_TOKEN` with read:packages to fetch the SDK from GitHub Packages. Check with `aapt2 dump badging` (label `Komboe`, package `io.komboe.android`).
