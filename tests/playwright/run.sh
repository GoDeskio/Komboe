#!/bin/sh
# Fresh fixtures, then the E2E run. Needs the HTTPS server (web vault refuses plain HTTP) on KOMBOE_WEB.
set -e; cd "$(dirname "$0")"
KOMBOE_URL=${KOMBOE_FIXTURE_URL:-http://127.0.0.1:8000} python3 fixtures.py
node e2e.mjs
# Desktop (Linux) E2E when a built linux-unpacked dir is given; attaches over CDP.
if [ -n "$KOMBOE_DESKTOP" ] && [ -x "$KOMBOE_DESKTOP/komboe" ]; then node desktop.mjs; fi
