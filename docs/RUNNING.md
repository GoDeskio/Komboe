<p align="center"><img alt="Komboe" src="../branding/wordmark/komboe-wordmark-light.svg" width="300"></p>

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
`./komboe --no-sandbox` (no user namespaces here). Smoke check: it launches on X11. Rebrand step 7 sets `extraMetadata.name = "komboe"`, `desktopName = komboe.desktop` and the desktop entry's
`StartupWMClass=komboe`, so the X11 window class is `komboe` (check: `xprop WM_CLASS` -> `"komboe", "komboe"`) and docks group it with its launcher.
`tests/playwright/desktop.mjs` launches the unpacked app with `--remote-debugging-port` and attaches with `chromium.connectOverCDP` (the release fuses block `--inspect`, but CDP works). Set `KOMBOE_DESKTOP=apps/desktop/dist/linux-unpacked`; `tests/playwright/run.sh` runs it after the web/extension suite.

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
`mobile/android_rebrand.py` swaps the launcher foreground and monochrome icons for padlock-K PNGs (adaptive icons override the mipmaps on API 26+). In-app logos (`logo_bitwarden` = header wordmark, `logo_shield_icon` = splash, `logo_bitwarden_icon`) must stay VectorDrawables because the app loads them with `rememberVectorPainter`; they are generated by `branding/wordmark/wordmark_lib.py` with compact relative path data (aapt2 rejects strings over 32 KB). The build needs `GITHUB_TOKEN` with read:packages to fetch the SDK from GitHub Packages. Check with `aapt2 dump badging` (label `Komboe`, package `io.komboe.android`).

## Brand: wordmark and font
The wordmark is the padlock-K mark plus "Komboe" set in **Sora** (SIL Open Font License 1.1, (c) 2019 The Sora Project Authors; no endorsement implied).
Text is outlined to paths, so the SVGs need no font. `branding/wordmark/build_wordmark.py` regenerates the SVG/PNG set (light, dark, mono). The web
vault, extension and desktop self-host `libs/components/src/webfonts/sora.woff2` (with `SORA-OFL.txt`) and use it for `h1` / `.komboe-brand` through
`--font-brand`. There is no Google Fonts CDN. `scripts/rebrand_apply.py` step 9 installs it.

## Alias mail forwarder (local-test)
`aliases/forwarder/komboe_forwarder.py` is a separate process (the server binary is unchanged). It reads aliases from the server DB read-only and handles
forwarding, block-sender, stats, multiple verified mailboxes, reverse-alias replies, PGP/MIME encryption, catch-all custom domains and directory subdomains.
Its management API is authenticated with the same `kmb_` alias API key.
```sh
pip install --target /workspace/tools/py aiosmtpd            # only dependency
PYTHONPATH=/workspace/tools/py SINK_DIR=/tmp/sink SINK_PORT=11025 python3 aliases/forwarder/smtp_sink.py &   # MailHog-style local sink
PYTHONPATH=/workspace/tools/py KOMBOE_DB=/workspace/run/data/db.sqlite3 FWD_RELAY=127.0.0.1:11025 FWD_SMTP_PORT=12525 FWD_API_PORT=18025 \
  FWD_TRUST_DOMAINS=1 python3 aliases/forwarder/komboe_forwarder.py
```
The feature suite starts both by itself (`tests/features/phase_e.py`). **Coverage is local-test only**: there is no MX record, no DNS TXT check for custom
domains (`FWD_TRUST_DOMAINS=1`, refused unless bound to loopback) and no SPF/DKIM/DMARC. Production needs those plus outbound DKIM signing.

## SAML SSO

Set `SSO_ENABLED=true`, `SSO_SAML_ENABLED=true`, `SSO_SAML_IDP_ENTITY_ID`, `SSO_SAML_IDP_SSO_URL`
(HTTP-Redirect SSO endpoint) and `SSO_SAML_IDP_CERT` (PEM text or path to the IdP signing cert).
Give the IdP the SP metadata at `{DOMAIN}/identity/saml/metadata` (ACS: `{DOMAIN}/identity/connect/saml-acs`).
The IdP must sign the Assertion; send the email as a `mail`/`email` attribute or an emailAddress NameID.
Set `SSO_SAML_EMAIL_VERIFIED=true` only if the IdP vouches for emails. SSO proves identity only; the
vault is still unlocked with the master password (or a trusted device), the server never gets the key.
Hardening (optional): `SSO_SAML_SP_KEY` + `SSO_SAML_SP_CERT` (PEM text or paths) sign AuthnRequests and
logout messages (RSA-SHA256, HTTP-Redirect) and let the IdP encrypt assertions to the SP cert (RSA-OAEP + AES;
RSA 1.5 refused). `SSO_SAML_REQUIRE_ENCRYPTED_ASSERTIONS=true` rejects plaintext assertions.
`SSO_SAML_IDP_SLO_URL` enables single logout: the IdP POSTs signed LogoutRequests to
`{DOMAIN}/identity/connect/saml-slo` (ends every session: devices/refresh tokens removed, security stamp
rotated), and clients call `POST /identity/connect/saml-logout` (bearer) to log out here and get the signed IdP
logout URL. No keys or IdP sessions are stored.
Tests: `tests/features/sso_saml.py`, `sso_saml_web.py`, `sso_saml_hardening.py` (need pysaml2 + xmlsec1).

## S3 attachments

Build with `cargo build --release --features sqlite,s3` and set
`ATTACHMENTS_FOLDER=s3://BUCKET/attachments?endpoint=https://s3.example&region=us-east-1` (AWS credentials from
the usual env/profile chain; add `&enable_virtual_host_style=false` for MinIO-style path addressing). Only client
ciphertext is stored. Test against a local moto S3 (no cloud account): `tests/features/s3_attachments.py`.
