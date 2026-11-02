#!/usr/bin/env bash
# student, консоль каждой собственной VM, cwd — домашний каталог.
set -euo pipefail
systemd-detect-virt --vm

if getent passwd cephops >/dev/null; then
  printf '%s\n' \
    'cephops уже существует: нужен маршрут проверки, не создания.' >&2
  exit 1
fi

sudo adduser --disabled-password --gecos '' cephops

sudo bash --noprofile --norc -c '
set -euo pipefail
set -o noclobber
umask 077
cat > /etc/sudoers.d/90-ceph-study-cephops.pending
' <<'EOF'
cephops ALL=(ALL:ALL) NOPASSWD: ALL
EOF

sudo visudo -cf /etc/sudoers.d/90-ceph-study-cephops.pending
sudo chmod 0440 /etc/sudoers.d/90-ceph-study-cephops.pending

sudo ln /etc/sudoers.d/90-ceph-study-cephops.pending \
  /etc/sudoers.d/90-ceph-study-cephops

sudo visudo -c
test "$(sudo -u cephops -H sudo -n id -u)" = 0
id cephops
