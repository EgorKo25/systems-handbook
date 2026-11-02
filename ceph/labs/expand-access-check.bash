# Source in reentered ceph1 Bash after console-rooted public inputs.
# In expand-access-01: ceph2/3/4.host-ed25519.pub and console-fingerprints.txt.
# Fingerprint file: exactly one "cephN SHA256:..." line for each N=2,3,4.
(
set -euo pipefail
umask 077
set -o noclobber
declare -F c >/dev/null
: "${fsid:?source reenter.bash}"
: "${image:?source reenter.bash}"
access="$HOME/ceph-study/access-01"
(cd "$access";sha256sum -c SHA256SUMS.access)
cd "$HOME/ceph-study/expand-access-01"
test ! -L "$PWD"
test "$(stat -c %u "$PWD")" = "$(id -u)"
test "$(stat -c %a "$PWD")" = 700
test "$(wc -l < console-fingerprints.txt)" = 3
: > known_hosts
for number in 2 3 4; do
 host="ceph$number"
 address="10.77.0.$((10+number))"
 pub="$host.host-ed25519.pub"
 actual=$(ssh-keygen -lf "$pub" -E sha256)
 test "$(printf '%s\n' "$actual" | wc -l)" = 1
 actual=$(printf '%s\n' "$actual" | awk '{print $2}')
 expected=$(awk -v h="$host" '$1==h {if(NF!=2)exit 1;n++;v=$2}END{if(n!=1)exit 1;print v}' console-fingerprints.txt)
 test "$actual" = "$expected"
 read -r kind encoded comment < "$pub"
 test "$kind" = ssh-ed25519
 test -n "$encoded"
 printf '%s %s %s\n' "$address" "$kind" "$encoded" >> known_hosts
done
trusted_ssh() {
 ssh -F /dev/null -o StrictHostKeyChecking=yes \
 -o UserKnownHostsFile="$PWD/known_hosts" -o GlobalKnownHostsFile=/dev/null \
 -o BatchMode=yes -o IdentitiesOnly=yes -o ConnectTimeout=10 \
 -o ConnectionAttempts=1 -i "$access/orchestrator_ed25519" "$@"
}
for number in 2 3 4; do
 host="ceph$number"
 address="10.77.0.$((10+number))"
 test "$(trusted_ssh "cephops@$address" hostname -s)" = "$host"
 test "$(trusted_ssh "cephops@$address" sudo -n id -u)" = 0
 trusted_ssh "cephops@$address" sudo -n cephadm check-host --expect-hostname "$host"
 trusted_ssh "cephops@$address" sudo -n bash -s -- "$image" <<'SH'
set -euo pipefail
cd /home/student/ceph-study/runtime-20.2.4-01
test "$(sed -n 's/^status=//p' RUNTIME-ACCEPTED.txt)" = accepted-runtime
sha256sum -c SHA256SUMS.runtime
test "$(cat ceph-image.txt)" = "$1"
test "$(dpkg-query -W -f='${Version}' cephadm)" = "$(cat cephadm-package.observed.txt)"
SH
done
sha256sum console-fingerprints.txt ceph2.host-ed25519.pub \
 ceph3.host-ed25519.pub ceph4.host-ed25519.pub known_hosts > SHA256SUMS.expand-access
printf '%s\n' 'status=accepted-manual-expand-access' > ACCESS-ACCEPTED.txt
)
