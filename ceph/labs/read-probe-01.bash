# Source reenter.bash first; run in that Bash.
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

mkdir -m 0700 "$HOME/ceph-study/read-probe-01"
cd "$HOME/ceph-study/read-probe-01"
r --pool cephstudy get "$key" - > readback.bin 2> get.stderr.txt
cmp -- "$origin/input/report.txt" readback.bin

sha256sum readback.bin > SHA256SUMS.read
printf 'status=accepted-read-probe\nfsid=%s\nobject=%s\n' \
  "$fsid" "$key" > READ-ACCEPTED.txt
