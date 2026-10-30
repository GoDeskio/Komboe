#!/usr/bin/env bash
# Import pinned upstream tags via git subtree. Excludes bitwarden_license/ (non-OSS).
# Usage: scripts/import-upstream.sh [clients|server|all]   (run from repo root, clean tree)
set -euo pipefail
BW_REPO=https://github.com/bitwarden/clients.git
BW_TAG="${BW_TAG:-web-v2026.10.0}"        # pin; see docs/UPSTREAM.md
VW_REPO=https://github.com/dani-garcia/vaultwarden.git
VW_TAG="${VW_TAG:-1.34.3}"                # pin; see docs/UPSTREAM.md
what="${1:-all}"
git diff --quiet && git diff --cached --quiet || { echo "tree not clean" >&2; exit 1; }

import() { # prefix repo tag
  local prefix=$1 repo=$2 tag=$3
  if [ -d "$prefix/upstream" ]; then git subtree pull --prefix="$prefix/upstream" "$repo" "$tag" --squash -m "Update $prefix to $tag"
  else git subtree add --prefix="$prefix/upstream" "$repo" "$tag" --squash -m "Import $prefix at $tag"; fi
}

if [[ $what == clients || $what == all ]]; then
  import clients "$BW_REPO" "$BW_TAG"
  if [ -d clients/upstream/bitwarden_license ]; then
    git rm -rq clients/upstream/bitwarden_license
    git commit -qm "Remove bitwarden_license/ (Bitwarden License, not OSS)"
  fi
fi
[[ $what == server || $what == all ]] && import server "$VW_REPO" "$VW_TAG"
scripts/check-licenses.sh
