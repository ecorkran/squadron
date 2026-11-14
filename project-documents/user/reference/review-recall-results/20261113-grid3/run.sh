#!/usr/bin/env bash
# Run one review: run.sh <case> <alias> <n>. Skips if the output exists.
# Needs WT (worktrees at each case head) and the provider key in the environment.
set -euo pipefail
case=$1 alias=$2 n=$3
here=$(cd "$(dirname "$0")" && pwd)
out="$here/$case-$alias-$n.json"
[ -s "$out" ] && exit 0
grep -qx "$alias" "$here/skip.txt" 2>/dev/null && exit 0  # deferred to a later batch
base=$(awk -v c="$case" '$1==c{print $3}' "$here/../20261112-grid2/cases.txt" "$here/cases-b2.txt")
[ -n "$base" ] || { echo "UNKNOWN CASE $case"; exit 1; }
cd "$WT/$case"
sq review code --diff "$base" --model "$alias" --no-save -v --output file --output-path "$out" \
  > "$here/logs/$case-$alias-$n.log" 2>&1 || true  # sq exits non-zero on a FAIL verdict
[ -s "$out" ] || echo "NO OUTPUT $case $alias $n: $(grep -m1 '^Error' "$here/logs/$case-$alias-$n.log" || echo 'no Error line in log')"
