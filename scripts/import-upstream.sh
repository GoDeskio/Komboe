#!/usr/bin/env bash
# Import pinned upstream tags as plain vendored snapshots (shallow clone + copy).
# bitwarden_license/ and LICENSE_BITWARDEN.txt are NEVER copied, so they never enter git history.
# Usage: scripts/import-upstream.sh [clients|server|aliases|all]   (run from repo root, clean tree)
set -euo pipefail
BW_REPO=https://github.com/bitwarden/clients.git
BW_TAG="${BW_TAG:-web-v2026.10.1}"   # = browser-v2026.10.1 = desktop-v2026.10.2 = cli-v2026.10.1
VW_REPO=https://github.com/dani-garcia/vaultwarden.git
VW_TAG="${VW_TAG:-1.37.4}"
SL_REPO=https://github.com/simple-login/app.git
SL_TAG="${SL_TAG:-v4.83.2}"
declare -A EXPECT=([$BW_TAG]=91214c3b978edb5496a32a946451960fe7d44531 [$VW_TAG]=7c188967e7a467b19b2757bc3326f9cf3ccae327 [$SL_TAG]=dc4130adc75e975cce74db4c1acbd9417105f60d)
what="${1:-all}"
git diff --quiet && git diff --cached --quiet || { echo "tree not clean" >&2; exit 1; }
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT

import() { # prefix repo tag
  local prefix=$1 repo=$2 tag=$3 src="$tmp/$1" got
  git clone -q --depth 1 --branch "$tag" "$repo" "$src"
  got=$(git -C "$src" rev-parse HEAD)
  [ "$got" = "${EXPECT[$tag]}" ] || { echo "tag $tag moved: $got (expected ${EXPECT[$tag]})" >&2; exit 1; }
  rm -rf "$prefix/upstream"; mkdir -p "$prefix/upstream"
  (cd "$src" && tar --exclude=./.git --exclude=./bitwarden_license --exclude=./LICENSE_BITWARDEN.txt -cf - .) | tar -xf - -C "$prefix/upstream"
  printf '%s %s %s\n' "$repo" "$tag" "$got" > "$prefix/UPSTREAM_PIN"
  git add -A "$prefix"
}
[[ $what == clients || $what == all ]] && import clients "$BW_REPO" "$BW_TAG"
[[ $what == server  || $what == all ]] && import server  "$VW_REPO" "$VW_TAG"
[[ $what == aliases || $what == all ]] && import aliases "$SL_REPO" "$SL_TAG"
scripts/check-licenses.sh
echo "Imported; review with: git status && git commit -m 'Import upstream ($what)'"
