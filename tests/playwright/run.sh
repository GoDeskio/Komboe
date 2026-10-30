#!/bin/sh
# Fresh fixtures, then the E2E run. Needs the HTTPS server (web vault refuses plain HTTP) on KOMBOE_WEB.
set -e; cd "$(dirname "$0")"
KOMBOE_URL=${KOMBOE_FIXTURE_URL:-http://127.0.0.1:8000} python3 fixtures.py
exec node e2e.mjs
