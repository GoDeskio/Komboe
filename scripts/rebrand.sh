#!/usr/bin/env bash
# Report (default) or apply (--apply) upstream branding replacements in imported trees.
# Never rewrites license headers, copyright lines, NOTICE, or docs/UPSTREAM.md.
set -euo pipefail
mode="${1:-report}"
paths=(clients/upstream server/upstream)
pattern='Bitwarden|bitwarden\.com|Vaultwarden|vaultwarden\.net'
if [ "$mode" = report ]; then
  git grep -nIE "$pattern" -- "${paths[@]}" ':!**/LICENSE*' | grep -viE 'copyright|license' | head -200 || true
  echo "--- logos/icons to replace:"; git ls-files "${paths[@]}" | grep -iE '(logo|icon|favicon).*\.(svg|png|ico)$' || true
  exit 0
fi
# --apply: user-visible strings + artwork only; protocol/API identifiers stay for compatibility.
exec python3 "$(dirname "$0")/rebrand_apply.py" "${@:2}"
