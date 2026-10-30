#!/bin/bash
set -euo pipefail
lab=$(realpath -- "${1:?Usage: start-dns.sh LAB_DIRECTORY}")
test -f "$lab/.course-dns" || { echo 'Not a course DNS directory' >&2; exit 1; }
for role in primary secondary resolver; do
  named-checkconf "$lab/$role.conf"
  if test -f "$lab/$role.pid" && kill -0 "$(cat "$lab/$role.pid")" 2>/dev/null; then
    echo "$role PID is still present; inspect it first" >&2; exit 1
  fi
done
python3 - <<'PY'
import socket
sockets = []
try:
    for port in (1053,2053,3053):
        for kind in (socket.SOCK_STREAM,socket.SOCK_DGRAM):
            listener=socket.socket(socket.AF_INET,kind)
            sockets.append(listener)
            listener.bind(('127.0.0.1',port))
except OSError as error:
    raise SystemExit('A laboratory port is unavailable: '+str(error))
finally:
    for listener in sockets: listener.close()
PY
started=()
cleanup_error() {
  code=$?
  if (( code != 0 )); then
    for pid in "${started[@]}"; do kill -TERM "$pid" 2>/dev/null || true; done
    echo "FAILED: inspect $lab/*.log; files retained" >&2
  fi
}
trap cleanup_error EXIT
for role in primary secondary resolver; do
  named -g -c "$lab/$role.conf" >"$lab/$role.log" 2>&1 &
  pid=$!
  started+=("$pid")
  printf '%s\n' "$pid" >"$lab/$role.pid"
  sleep 1
  kill -0 "$pid" || { tail -n 20 "$lab/$role.log" >&2; exit 1; }
  printf '%s PID=%s LOG=%s\n' "$role" "$pid" "$lab/$role.log"
done
echo 'STARTED: verify with dig; startup alone is not a DNS answer test'
