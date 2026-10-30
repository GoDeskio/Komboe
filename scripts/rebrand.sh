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
# --apply: user-visible strings only; protocol/API identifiers stay for compatibility.
git grep -lIE 'Bitwarden' -- "${paths[@]}" '*.json' '*.html' '*.ts' ':!**/LICENSE*' \
  | xargs -r sed -i -E '/[Cc]opyright|[Ll]icense/!s/"(appName|name|title)": "Bitwarden/"\1": "Komboe/g'
echo "Applied safe string pass. Finish manually with branding/REBRAND-CHECKLIST.md"
