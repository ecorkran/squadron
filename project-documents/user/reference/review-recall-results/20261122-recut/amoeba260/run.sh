#!/usr/bin/env bash
# One tasks review of amoeba slice 260's task file as it stood at amoeba 1be45d3a: run.sh <case-tree> <alias> <n>.
set -uo pipefail
tree=$1 alias=$2 n=$3
here=$(cd "$(dirname "$0")" && pwd)
out="$here/out/amoeba260-$alias-$n.json"
[ -s "$out" ] && exit 0
# sq reads provider keys from the .env of its working directory; the case tree has none, so load squadron's.
set -a; . "$here/../../../../../../.env"; set +a
cd "$tree" || exit 1
start=$(date +%s)
/Users/manta/.local/bin/sq review tasks project-documents/user/tasks/260-tasks.hub-and-door.md --against project-documents/user/slices/260-slice.hub-and-door.md \
  --model "$alias" --no-save -v --output file --output-path "$out" > "$here/logs/amoeba260-$alias-$n.log" 2>&1 || true  # non-zero on FAIL
if [ -s "$out" ]; then echo "done $alias $n $(( $(date +%s) - start ))s"; else echo "NO OUTPUT $alias $n: $(grep -m1 -i 'error' "$here/logs/amoeba260-$alias-$n.log" || echo 'no error line')"; fi
