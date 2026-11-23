#!/usr/bin/env bash
# One document review on a mined case with the installed squadron: run.sh <work-dir> <case> <alias> <n>.
# Skips if the output exists. The case list and against-documents are ../20261116-mined/against.tsv.
set -euo pipefail
work=$1 case=$2 alias=$3 n=$4
here=$(cd "$(dirname "$0")" && pwd)
out="$here/out/$case-$alias-$n.json"
[ -s "$out" ] && exit 0
IFS=$'\t' read -r _ kind doc against < <(awk -F'\t' -v c="$case" '$1==c' "$here/../20261116-mined/against.tsv")
[ -n "${kind:-}" ] && [ -n "${doc:-}" ] || { echo "UNKNOWN CASE $case"; exit 1; }
args=("$kind" "$doc" --model "$alias" --no-save -v --output file --output-path "$out")
[ "$against" != "-" ] && args+=(--against "$against")
cd "$work/wt/$case" || exit 1
mkdir -p "$here/out" "$here/logs"
start=$(date +%s)
/Users/manta/.local/bin/sq review "${args[@]}" > "$here/logs/$case-$alias-$n.log" 2>&1 || true  # non-zero on FAIL
if [ -s "$out" ]; then echo "done $case $alias $n $(( $(date +%s) - start ))s"
else echo "NO OUTPUT $case $alias $n: $(grep -m1 -i 'error' "$here/logs/$case-$alias-$n.log" || echo 'no error line in log')"; fi
