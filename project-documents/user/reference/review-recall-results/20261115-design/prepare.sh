#!/usr/bin/env bash
# Export each case's tree at its reviewed commit into a one-commit scratch repo (no history,
# no saved reviews), and print the document each review runs against.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
repo=/Users/manta/source/repos/manta/squadron
while read -r case sha kind doc; do
  dir="$here/wt/$case"
  rm -rf "$dir"; mkdir -p "$dir"
  git -C "$repo" archive "$sha" | tar -x -C "$dir"
  [ -f "$dir/$doc" ] || { echo "MISSING DOC $case $doc"; exit 1; }
  rm -rf "$dir/project-documents/user/reviews"
  git -C "$dir" init -q -b main
  git -C "$dir" add -A
  git -C "$dir" -c user.name=bench -c user.email=bench@example.invalid commit -q -m "case tree"
  if [ "$kind" = slice ]; then key=parent; else key=lld; fi
  against=$(awk -v k="$key:" '$1==k{print $2; exit}' "$dir/$doc")
  echo "$case $kind against=$against"
done < "$here/cases.txt"
