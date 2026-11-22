#!/usr/bin/env bash
# One code review on a benchmark sandbox, with variants: run_review.sh <case-name> <alias> <n>. Skips if the output exists.
# REVIEW_LABEL names the output (default: the alias); REVIEW_RULES adds a rules file; REVIEW_NO_TOOLS=1 runs without tools.
set -euo pipefail
name=$1 alias=$2 n=$3
here=$(cd "$(dirname "$0")" && pwd)
label=${REVIEW_LABEL:-$alias}
out="$here/out/$name-$label-$n.json"
[ -s "$out" ] && exit 0
read -r box base < <(python3 - "$here/cases.json" "$name" <<'PY'
import json, sys
for case in json.load(open(sys.argv[1])).values():
    if case["name"] == sys.argv[2]:
        print(case["sandbox"], case["base_local"])
PY
)
[ -d "${box:-}" ] || { echo "UNKNOWN CASE $name"; exit 1; }
# sq reads provider keys from the .env of its working directory; the sandbox has none, so load squadron's.
set -a; . "$here/../../../../../.env"; set +a
extra=()
[ -n "${REVIEW_RULES:-}" ] && extra+=(--rules "$REVIEW_RULES")
[ -n "${REVIEW_NO_TOOLS:-}" ] && extra+=(--no-tools)
cd "$box" || exit 1
start=$(date +%s)
/Users/manta/.local/bin/sq review code --diff "$base" --model "$alias" --no-save -v --output file --output-path "$out" --cwd . ${extra[@]+"${extra[@]}"} > "$here/logs/$name-$label-$n.log" 2>&1 || true  # non-zero on FAIL
if [ -s "$out" ]; then echo "done $name $label $n $(( $(date +%s) - start ))s"
else echo "NO OUTPUT $name $label $n: $(grep -m1 -i 'error' "$here/logs/$name-$label-$n.log" || echo 'no error line in log')"; fi
