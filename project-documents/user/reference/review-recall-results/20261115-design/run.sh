#!/usr/bin/env bash
# Run one review: run.sh <case> <alias> <n>. Skips if the output exists.
set -uo pipefail
case=$1 alias=$2 n=$3
here=$(cd "$(dirname "$0")" && pwd)
out="$here/out/$case-$alias-$n.json"
[ -s "$out" ] && exit 0
read -r _ _ kind doc < <(awk -v c="$case" '$1==c' "$here/cases.txt")
against=$(awk -v c="$case" '$1==c{print $2}' "$here/against.txt")
[ -n "$kind" ] && [ -n "$against" ] || { echo "UNKNOWN CASE $case"; exit 1; }
cd "$here/wt/$case" || exit 1
start=$(date +%s)
/Users/manta/.local/bin/sq review "$kind" "$doc" --against "$against" --model "$alias" --no-save -v \
  --output file --output-path "$out" > "$here/logs/$case-$alias-$n.log" 2>&1 || true  # non-zero on FAIL
if [ -s "$out" ]; then echo "done $case $alias $n $(( $(date +%s) - start ))s"
else echo "NO OUTPUT $case $alias $n: $(grep -m1 -i 'error' "$here/logs/$case-$alias-$n.log" || echo 'no error line in log')"; fi
