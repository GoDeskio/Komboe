#!/usr/bin/env bash
# Import pinned upstream tags via git subtree. Excludes bitwarden_license/ (non-OSS).
# Usage: scripts/import-upstream.sh [clients|server|aliases|all]   (run from repo root, clean tree)
set -euo pipefail
BW_REPO=https://github.com/bitwarden/clients.git
BW_TAG="${BW_TAG:-web-v2026.10.1}"   # = browser-v2026.10.1 = desktop-v2026.10.2 = cli-v2026.10.1 @ 91214c3b978edb5496a32a946451960fe7d44531
VW_REPO=https://github.com/dani-garcia/vaultwarden.git
VW_TAG="${VW_TAG:-1.37.4}"           # @ 7c188967e7a467b19b2757bc3326f9cf3ccae327
SL_REPO=https://github.com/simple-login/app.git
SL_TAG="${SL_TAG:-v4.83.2}"           # @ dc4130adc75e975cce74db4c1acbd9417105f60d
# Expected commit SHAs; import aborts if a tag moved.
declare -A EXPECT=([$BW_TAG]=91214c3b978edb5496a32a946451960fe7d44531 [$VW_TAG]=7c188967e7a467b19b2757bc3326f9cf3ccae327 [$SL_TAG]=dc4130adc75e975cce74db4c1acbd9417105f60d)
verify() { local got; got=$(git ls-remote "$1" "refs/tags/$2^{}" | cut -f1); [ -n "$got" ] || got=$(git ls-remote "$1" "refs/tags/$2" | cut -f1)
  [ -z "${EXPECT[$2]:-}" ] || [ "$got" = "${EXPECT[$2]}" ] || { echo "tag $2 moved: $got" >&2; exit 1; }; }
what="${1:-all}"
git diff --quiet && git diff --cached --quiet || { echo "tree not clean" >&2; exit 1; }

import() { # prefix repo tag
  local prefix=$1 repo=$2 tag=$3
  verify "$repo" "$tag"
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
[[ $what == aliases || $what == all ]] && import aliases "$SL_REPO" "$SL_TAG"
scripts/check-licenses.sh
