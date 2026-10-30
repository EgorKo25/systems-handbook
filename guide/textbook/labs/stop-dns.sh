#!/bin/bash
set -euo pipefail
lab=$(realpath -- "${1:?Usage: stop-dns.sh LAB_DIRECTORY}")
test -f "$lab/.course-dns" || { echo 'Not a course DNS directory' >&2; exit 1; }
for role in resolver secondary primary; do
  file="$lab/$role.pid"
  test -f "$file" || continue
  pid=$(cat "$file")
  [[ "$pid" =~ ^[0-9]+$ ]] || { echo "Invalid PID: $file" >&2; exit 1; }
  if ! test -d "/proc/$pid"; then echo "$role already stopped"; continue; fi
  mapfile -d '' -t argv <"/proc/$pid/cmdline"
  matched=false
  for arg in "${argv[@]}"; do
    if [[ "$arg" == "$lab/$role.conf" ]]; then matched=true; fi
  done
  if [[ "$matched" != true || "${argv[0]##*/}" != named ]]; then
    echo "PID $pid is not this named instance; not touching it" >&2; exit 1
  fi
  kill -TERM "$pid"
  echo "TERM sent: $role PID=$pid"
done
echo 'Configuration and logs retained; no directory was deleted'
