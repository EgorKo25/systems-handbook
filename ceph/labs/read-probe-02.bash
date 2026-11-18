# Source reenter.bash first; run after verified expansion.
# Pass a fresh output name such as read-probe-02 or read-probe-02-after-change.
(
set -euo pipefail
umask 077
set -o noclobber

origin="$HOME/ceph-study/rados-01"
(
  cd "$origin"
  test "$(sed -n 's/^status=//p' RADOS-ACCEPTED.txt)" = accepted-rados-roundtrip
  sha256sum -c SHA256SUMS.inputs
  sha256sum -c SHA256SUMS.rados
)

test "$(cat "$origin/fsid.txt")" = "$fsid"
key=$(cat "$origin/object-key.txt")

output=${1-read-probe-02}
if (( $# > 1 )) || [[ ! $output =~ ^read-probe-02(-[a-z0-9][a-z0-9-]{0,39})?$ ]]; then
  printf '%s\n' 'Use read-probe-02 or read-probe-02-SUFFIX (lowercase letters, digits, hyphens).' >&2
  exit 2
fi
mkdir -m 0700 "$HOME/ceph-study/$output"
cd "$HOME/ceph-study/$output"

r --pool cephstudy get "$key" - > readback.bin 2> get.stderr.txt
cmp -- "$origin/input/report.txt" readback.bin
sha256sum readback.bin > SHA256SUMS.read
printf 'status=accepted-read-probe\nfsid=%s\nobject=%s\n' \
  "$fsid" "$key" > READ-ACCEPTED.txt
)
