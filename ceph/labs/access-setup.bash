# Run numbered blocks in the console of your own ceph1 as student.
# Prerequisites: accepted runtime, cephops + visudo + local sudo -n.
# A. Create once; stop if access-01 exists.
set -euo pipefail
umask 077
set -o noclobber
systemd-detect-virt --vm >/dev/null
test "$(hostname -s)" = ceph1
cd "$HOME/ceph-study"
mkdir -m 0700 access-01
cd access-01
ssh-keygen -t ed25519 -N '' -C ceph-study-orchestrator-01 -f "$PWD/orchestrator_ed25519"
ssh-keygen -lf orchestrator_ed25519.pub -E sha256
# B. Still in this VM console, install only its public half.
sudo -u cephops -H bash --noprofile --norc -c '
set -euo pipefail
set -o noclobber
umask 077
mkdir -m 0700 "$HOME/.ssh"
cat > "$HOME/.ssh/authorized_keys"
' < orchestrator_ed25519.pub
# C. Read host identity directly from this VM console.
hostname -s
ip -br address
sudo ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub -E sha256
sudo cat /etc/ssh/ssh_host_ed25519_key.pub > ceph1.host-ed25519.pub
ssh-keygen -lf ceph1.host-ed25519.pub -E sha256
# Compare the two full fingerprints before continuing.
read -r kind encoded comment < ceph1.host-ed25519.pub
test "$kind" = ssh-ed25519
test -n "$encoded"
printf '10.77.0.11 %s %s\n' "$kind" "$encoded" > known_hosts
trusted_ssh() {
 ssh -F /dev/null -o StrictHostKeyChecking=yes \
  -o UserKnownHostsFile="$PWD/known_hosts" -o GlobalKnownHostsFile=/dev/null \
  -o BatchMode=yes -o IdentitiesOnly=yes -o ConnectTimeout=10 \
  -o ConnectionAttempts=1 -i "$PWD/orchestrator_ed25519" "$@"
}
test "$(trusted_ssh cephops@10.77.0.11 hostname -s)" = ceph1
test "$(trusted_ssh cephops@10.77.0.11 sudo -n id -u)" = 0
trusted_ssh cephops@10.77.0.11 sudo -n cephadm check-host --expect-hostname ceph1
sha256sum orchestrator_ed25519 orchestrator_ed25519.pub \
 ceph1.host-ed25519.pub known_hosts > SHA256SUMS.access
printf '%s\n' 'status=accepted-access' 'hosts=ceph1' > ACCESS-ACCEPTED.txt
