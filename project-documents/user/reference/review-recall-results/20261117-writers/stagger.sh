#!/usr/bin/env bash
# Launch jobs 20 s apart: concurrent `cf init` calls race on context-forge's project registry.
here=$(cd "$(dirname "$0")" && pwd)
while read -r phase slice config; do
  "$here/run.sh" "$phase" "$slice" "$config" >> "$here/batch.log" 2>&1 &
  sleep 20
done < "$1"
wait
