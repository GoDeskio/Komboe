#!/bin/bash
# Start the Komboe server and the marketing site, then sign in from the home page.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$(cd ../.. && pwd)"
BIN="${KOMBOE_BIN:-$ROOT/server/upstream/target/debug/vaultwarden}"
if [[ ! -x "$BIN" ]]; then
  (cd "$ROOT/server/upstream" && cargo build --features sqlite)
fi
DATA="$(mktemp -d)"
API_PORT="${KOMBOE_API_PORT:-18080}"
WEB_PORT="${KOMBOE_WEB_PORT:-4173}"
API_PID=""
WEB_PID=""
cleanup() {
  [[ -n "$WEB_PID" ]] && kill "$WEB_PID" 2>/dev/null || true
  [[ -n "$API_PID" ]] && kill "$API_PID" 2>/dev/null || true
  rm -rf "$DATA"
}
trap cleanup EXIT
# A non-empty SMTP_FROM without SMTP_HOST refuses to boot. Mail stays off so
# account creation returns the verification token directly.
env -u SMTP_HOST -u SMTP_USERNAME -u SMTP_PASSWORD -u ADMIN_TOKEN \
  SMTP_FROM= \
  DATA_FOLDER="$DATA" ROCKET_ADDRESS=127.0.0.1 ROCKET_PORT="$API_PORT" \
  SIGNUPS_ALLOWED=true WEB_VAULT_ENABLED=false DOMAIN="http://127.0.0.1:$WEB_PORT" \
  "$BIN" >"$DATA/server.log" 2>&1 &
API_PID=$!
for _ in $(seq 1 80); do
  if curl -fsS "http://127.0.0.1:$API_PORT/alive" >/dev/null 2>&1; then break; fi
  sleep 0.25
done
curl -fsS "http://127.0.0.1:$API_PORT/alive" >/dev/null
python3 serve.py --host 127.0.0.1 --port "$WEB_PORT" --api "http://127.0.0.1:$API_PORT" >"$DATA/web.log" 2>&1 &
WEB_PID=$!
for _ in $(seq 1 40); do
  if curl -fsS "http://127.0.0.1:$WEB_PORT/" >/dev/null 2>&1; then break; fi
  sleep 0.2
done
mkdir -p e2e/screenshots
KOMBOE_API="http://127.0.0.1:$API_PORT" KOMBOE_WEB="http://127.0.0.1:$WEB_PORT" \
  npx playwright test
