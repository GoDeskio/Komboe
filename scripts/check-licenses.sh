#!/usr/bin/env bash
# Fails if any Bitwarden License code is present, or LICENSE is not AGPL-3.0.
set -euo pipefail
fail=0
if git ls-files | grep -q '(^|/)bitwarden_license/' -E; then echo "ERROR: bitwarden_license/ code present" >&2; fail=1; fi
if git grep -lI 'Bitwarden License Agreement' -- . ':!scripts/' ':!docs/' ':!THIRD-PARTY-NOTICES.md' >/dev/null 2>&1; then echo "ERROR: Bitwarden License text found" >&2; fail=1; fi
grep -q 'GNU AFFERO GENERAL PUBLIC LICENSE' LICENSE || { echo "ERROR: LICENSE not AGPL-3.0" >&2; fail=1; }
[ $fail = 0 ] && echo "license check OK"; exit $fail
