# Source this file in Bash inside ceph1. No constructor is called.
set -euo pipefail
systemd-detect-virt --vm >/dev/null
test "$(hostname -s)" = ceph1
study_root="$HOME/ceph-study"
supply="$study_root/supply-20.2.4-01"
runtime="$study_root/runtime-20.2.4-01"
for input_dir in "$study_root" "$supply" "$runtime" "$study_root/bootstrap-01"; do
  test -d "$input_dir"
  test ! -L "$input_dir"
  test "$(stat -c %u "$input_dir")" = "$(id -u)"
  test "$(stat -c %a "$input_dir")" = 700
done
(cd "$supply"
 test "$(sed -n 's/^status=//p' SIGNATURE-ACCEPTED.txt)" = accepted-signature-inputs
 sha256sum -c SHA256SUMS.signature)
(cd "$runtime"
 test "$(sed -n 's/^status=//p' RUNTIME-ACCEPTED.txt)" = accepted-runtime
 sha256sum -c SHA256SUMS.runtime)
test "$(dpkg-query -W -f='${Version}' cephadm)" = "$(cat "$runtime/cephadm-package.observed.txt")"
cd "$study_root/bootstrap-01"
test "$(sed -n 's/^status=//p' BOOTSTRAP-ACCEPTED.txt)" = accepted-bootstrap
sha256sum -c SHA256SUMS.inputs
sha256sum -c SHA256SUMS.bootstrap
fsid=$(cat fsid.planned.txt)
image=$(cat ceph-image.txt)
test "$image" = "$(cat "$runtime/ceph-image.txt")"
python3 -B - "$fsid" "$image" <<'PY'
import re, sys, uuid
if str(uuid.UUID(sys.argv[1])) != sys.argv[1]:
    raise SystemExit("bad fsid")
if not re.fullmatch(r"quay\.io/ceph/ceph@sha256:[0-9a-f]{64}", sys.argv[2]):
    raise SystemExit("bad image")
PY
c() { sudo cephadm --image "$image" shell --fsid "$fsid" -- ceph "$@"; }
r() { sudo cephadm --image "$image" shell --fsid "$fsid" -- rados "$@"; }
b() { sudo cephadm --image "$image" shell --fsid "$fsid" -- rbd "$@"; }
test "$(c fsid)" = "$fsid"
c status
c health detail
