#!/bin/bash
set -euo pipefail
(( EUID == 0 )) || { echo 'Run as root on the learning VM' >&2; exit 1; }
for ns in course-c course-r course-s; do
  if ip netns list | awk '{print $1}' | grep -Fxq "$ns"; then
    processes=$(ip netns pids "$ns")
    if [[ -n "$processes" ]]; then
      echo "Stop the lab processes in $ns first: $processes" >&2; exit 1
    fi
  fi
done
for ns in course-c course-r course-s; do
  if ip netns list | awk '{print $1}' | grep -Fxq "$ns"; then ip netns del "$ns"; fi
done
echo 'Removed the three named learning namespaces; host networking unchanged'
