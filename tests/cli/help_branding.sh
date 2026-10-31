#!/bin/sh
# CLI help must say "Usage: komboe" and show no "bw <command>" examples.
set -e
BW="${BW:-$(dirname "$0")/../../clients/upstream/apps/cli/build/bw.js}"
for c in "" list get create edit send serve login unlock encode; do
  out=$(node "$BW" $c --help 2>&1)
  echo "$out" | grep -q "Usage: komboe" || { echo "FAIL: $c usage"; exit 1; }
  if echo "$out" | grep -qE '(^|[ |$`])bw [a-z]'; then echo "FAIL: $c has bw example"; exit 1; fi
done
echo "CLI HELP PASS"
