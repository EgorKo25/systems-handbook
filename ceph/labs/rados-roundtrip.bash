# Source reenter.bash first; run in that Bash.
set -euo pipefail
umask 077
set -o noclobber

mkdir -m 0700 "$HOME/ceph-study/rados-01"
cd "$HOME/ceph-study/rados-01"
mkdir -m 0700 input

printf '%s\n' 'Ceph Tentacle 20.2.4: one verified RADOS object.' > input/report.txt
key="report-$(cat /proc/sys/kernel/random/uuid)"
printf '%s\n' "$key" > object-key.txt
printf '%s\n' "$fsid" > fsid.txt
sha256sum input/report.txt object-key.txt fsid.txt > SHA256SUMS.inputs
printf 'status=attempted\nobject=%s\n' "$key" > OPERATION-ATTEMPTED.txt

r --pool cephstudy create "$key"

sudo cephadm --image "$image" shell --fsid "$fsid" \
  --mount "$PWD/input:/study-input:ro" -- \
  rados --pool cephstudy put "$key" /study-input/report.txt \
  > put.stdout.txt 2> put.stderr.txt

r --pool cephstudy get "$key" - > readback.bin 2> get.stderr.txt
cmp -- input/report.txt readback.bin

sha256sum input/report.txt readback.bin object-key.txt fsid.txt > SHA256SUMS.rados
printf 'status=accepted-rados-roundtrip\nfsid=%s\nobject=%s\n' \
  "$fsid" "$key" > RADOS-ACCEPTED.txt
