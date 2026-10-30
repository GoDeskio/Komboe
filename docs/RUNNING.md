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
Currently 8/9 steps pass; `extension-loads` fails because branded Chrome ignores `--load-extension`.

## CLI (local testing only)
```sh
export BITWARDENCLI_APPDATA_DIR=/tmp/kcli NODE_EXTRA_CA_CERTS=tls/cert.pem
komboe-cli-linux-x64 config server https://localhost:8443
komboe-cli-linux-x64 login you@example.test --passwordenv KPW --raw   # prints session
komboe-cli-linux-x64 list items --session <session>
```
Build: `NODE_ENV=production npx webpack` in `apps/cli`, then `npx pkg . --targets node22-linux-x64`.
The binary still uses upstream names internally (`bw`, "Bitwarden CLI" app-data dir): rebrand pending.

## Not buildable on this box
- Desktop (Electron): `desktop_native` needs pkg-config + libdbus/libsecret dev headers, which aren't installed (apt is broken here).
- Android: no JDK or Android SDK.
