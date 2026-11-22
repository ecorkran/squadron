#!/usr/bin/env bash
# Run one code review on a benchmark sandbox: run.sh <case-name> <alias> <n>. Skips if the output exists.
set -uo pipefail
name=$1 alias=$2 n=$3
here=$(cd "$(dirname "$0")" && pwd)
out="$here/out/$name-$alias-$n.json"
[ -s "$out" ] && exit 0
read -r box base < <(python3 - "$here/cases.json" "$name" <<'PY'
import json, sys
for case in json.load(open(sys.argv[1])).values():
    if case["name"] == sys.argv[2]:
        print(case["sandbox"], case["base_local"])
PY
)
[ -n "${box:-}" ] && [ -d "$box" ] || { echo "UNKNOWN CASE $name"; exit 1; }
# sq reads provider keys from the .env of its working directory; the sandbox has none, so load squadron's.
env_file="$here/../../../../../.env"
[ -f "$env_file" ] && { set -a; . "$env_file"; set +a; }
cd "$box" || exit 1
start=$(date +%s)
/Users/manta/.local/bin/sq review code --diff "$base" --model "$alias" --no-save -v --output file --output-path "$out" --cwd . > "$here/logs/$name-$alias-$n.log" 2>&1 || true  # non-zero on FAIL
if [ -s "$out" ]; then echo "done $name $alias $n $(( $(date +%s) - start ))s"
else echo "NO OUTPUT $name $alias $n: $(grep -m1 -i 'error' "$here/logs/$name-$alias-$n.log" || echo 'no error line in log')"; fi
