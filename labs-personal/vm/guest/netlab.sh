#!/usr/bin/env bash
# Real Linux network stacks inside ONE study VM. Never run on the physical host.
set -euo pipefail
action=${1:-help}
if [[ ${2:-} != --inside-lab-vm ]]; then
  printf '%s\n' 'Inside study VM only: sudo bash netlab.sh up|check|down --inside-lab-vm' >&2
  exit 2
fi
virt=$(systemd-detect-virt --vm || true)
if [[ $virt != kvm && $virt != qemu ]] || [[ $EUID -ne 0 ]]; then
  printf '%s\n' 'Refused: root inside a QEMU/KVM study guest is required.' >&2
  exit 2
fi
names=(study-client study-router study-server)
case "$action" in
  up)
    for name in "${names[@]}"; do
      if ip netns list | awk '{print $1}' | grep -Fxq -- "$name"; then
        printf 'Refused: %s already exists; current exercise was not reset.\n' "$name" >&2
        exit 2
      fi
    done
    for name in "${names[@]}"; do ip netns add "$name"; done
    ip link add study-c0 type veth peer name study-r0
    ip link set study-c0 netns study-client
    ip link set study-r0 netns study-router
    ip link add study-r1 type veth peer name study-s0
    ip link set study-r1 netns study-router
    ip link set study-s0 netns study-server
    for name in "${names[@]}"; do ip -n "$name" link set lo up; done
    ip -n study-client address add 10.44.10.10/24 dev study-c0
    ip -n study-client link set study-c0 up
    ip -n study-client route add default via 10.44.10.1
    ip -n study-router address add 10.44.10.1/24 dev study-r0
    ip -n study-router address add 10.44.30.1/24 dev study-r1
    ip -n study-router link set study-r0 up
    ip -n study-router link set study-r1 up
    ip netns exec study-router sysctl -q -w net.ipv4.ip_forward=0
    ip -n study-server address add 10.44.30.10/24 dev study-s0
    ip -n study-server link set study-s0 up
    ip -n study-server route add default via 10.44.30.1
    printf '%s\n' 'Created. Router forwarding is deliberately OFF: first diagnose it.'
    ;;
  check)
    for name in "${names[@]}"; do
      printf '\n%s\n' "$name"
      ip -n "$name" -brief address
      ip -n "$name" route show
    done
    ip netns exec study-router sysctl net.ipv4.ip_forward
    printf '%s\n' 'Client→gateway must work; end-to-end requires your router configuration.'
    ip netns exec study-client ping -n -c 1 -W 1 10.44.10.1
    ;;
  down)
    if [[ ${3:-} != --confirm-netlab ]]; then
      printf '%s\n' 'Stop your namespace processes first, then add --confirm-netlab.' >&2
      exit 2
    fi
    for name in "${names[@]}"; do
      if [[ -n $(ip netns pids "$name") ]]; then
        printf 'Refused: processes still run in %s. No process was killed.\n' "$name" >&2
        exit 2
      fi
    done
    for name in "${names[@]}"; do ip netns delete "$name"; done
    printf '%s\n' 'Only the three study-* namespaces were removed.'
    ;;
  *) printf '%s\n' 'Actions: up, check, down. See NETWORK-EXERCISES.txt.'; exit 2 ;;
esac
