#!/usr/bin/env bash
# Optional batch preparation for a repeat experiment INSIDE the lab VM.
# The main practicum installs tools at their first encounter. Requires internet.
set -euo pipefail
if [[ ${1:-} != --inside-lab-vm ]]; then
  printf '%s\n' 'Run only in the study VM: sudo bash bootstrap.sh --inside-lab-vm' >&2
  exit 2
fi
virt=$(systemd-detect-virt --vm || true)
if [[ $virt != kvm && $virt != qemu ]]; then
  printf 'Refused: QEMU/KVM guest expected, got %s\n' "$virt" >&2
  exit 2
fi
if [[ $EUID -ne 0 ]]; then
  printf '%s\n' 'Root is required inside the guest.' >&2
  exit 2
fi
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
  openssh-server ca-certificates bash-completion iproute2 iputils-ping \
  tcpdump nftables dnsutils curl jq git python3 strace lsof procps psmisc \
  netcat-openbsd iperf3 dnsmasq-base e2fsprogs parted lvm2
systemctl enable ssh
systemctl enable serial-getty@ttyS0.service
install -d -m 0755 /srv/study/{app,data,backups,exercises}
printf '%s\n' 'Base tools prepared. Create your own SSH key/password and check access before leaving home.'
printf '%s\n' 'Docker is not installed here. Follow the official Ubuntu Docker instructions INSIDE this VM.'
