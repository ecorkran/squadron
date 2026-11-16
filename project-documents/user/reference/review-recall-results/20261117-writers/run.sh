#!/usr/bin/env bash
# run.sh <phase> <slice> <config>: one writer replay, reviewer fixed, one revision round.
set -uo pipefail
phase=$1 slice=$2 config=$3
here=$(cd "$(dirname "$0")" && pwd)
log="$here/logs/$phase-$slice-$config.log"
cd /Users/manta/source/repos/manta/squadron || exit 1
start=$(date +%s)
/Users/manta/.local/bin/sq replay run --phase "$phase" --slice "$slice" --config "$config" \
  --reviewer haiku-xhigh --max-revisions 1 --yes > "$log" 2>&1
echo "exit $? $phase $slice $config $(( $(date +%s) - start ))s"
