#!/bin/bash
set -euo pipefail
(( EUID == 0 )) || { echo 'Run as root on an isolated learning VM' >&2; exit 1; }
for command in ip sysctl; do command -v "$command" >/dev/null; done
for ns in course-c course-r course-s; do
  if ip netns list | awk '{print $1}' | grep -Fxq "$ns"; then
    echo "Namespace $ns already exists; refusing to reuse it" >&2; exit 1
  fi
done
created=()
cleanup_error() {
  code=$?
  if (( code != 0 )); then
    for ns in "${created[@]}"; do ip netns del "$ns" || true; done
    echo 'FAILED: only namespaces created by this run were removed' >&2
  fi
}
trap cleanup_error EXIT
for ns in course-c course-r course-s; do
  ip netns add "$ns"; created+=("$ns")
  ip -n "$ns" link set lo up
done
# Create both ends directly in the owned namespaces: no physical NIC changes.
ip -n course-c link add c0 type veth peer name left netns course-r
ip -n course-s link add s0 type veth peer name right netns course-r
ip -n course-c addr add 198.18.1.2/24 dev c0
ip -n course-r addr add 198.18.1.1/24 dev left
ip -n course-r addr add 198.18.2.1/24 dev right
ip -n course-s addr add 198.18.2.2/24 dev s0
ip -n course-c link set c0 up
ip -n course-r link set left up
ip -n course-r link set right up
ip -n course-s link set s0 up
ip -n course-c route add default via 198.18.1.1
ip -n course-s route add default via 198.18.2.1
# This sysctl is scoped to course-r, not the host network namespace.
ip netns exec course-r sysctl -w net.ipv4.ip_forward=1
echo 'READY: course-c -> course-r -> course-s; no NAT yet'
