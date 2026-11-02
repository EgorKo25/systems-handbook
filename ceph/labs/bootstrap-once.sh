#!/usr/bin/env bash
# Only inside ceph1 after runtime and access acceptance.
set -euo pipefail
umask 077
set -o noclobber

systemd-detect-virt --vm >/dev/null
test "$(hostname -s)" = ceph1
test "$(timedatectl show -p NTPSynchronized --value)" = yes

ip -4 -json address show | python3 -B -c '
import json, sys
addresses = [
    a.get("local")
    for i in json.load(sys.stdin)
    for a in i.get("addr_info", [])
]
if "10.77.0.11" not in addresses:
    raise SystemExit("wrong VM address")
'

root_dir="$HOME/ceph-study"
runtime="$root_dir/runtime-20.2.4-01"
access="$root_dir/access-01"

for input_dir in "$root_dir" "$runtime" "$access"; do
  test -d "$input_dir"
  test ! -L "$input_dir"
  test "$(stat -c %u "$input_dir")" = "$(id -u)"
  test "$(stat -c %a "$input_dir")" = 700
done

(
  cd "$runtime"
  test "$(sed -n 's/^status=//p' RUNTIME-ACCEPTED.txt)" = accepted-runtime
  sha256sum -c SHA256SUMS.runtime
)
(
  cd "$access"
  test "$(sed -n 's/^status=//p' ACCESS-ACCEPTED.txt)" = accepted-access
  sha256sum -c SHA256SUMS.access
)

image=$(cat "$runtime/ceph-image.txt")
test "$(sudo -u cephops -H sudo -n id -u)" = 0

if sudo test -e /etc/ceph/ceph.conf ||
   sudo test -L /etc/ceph/ceph.conf; then
  printf '%s\n' 'Existing cluster config: inspect it; bootstrap is forbidden here.' >&2
  exit 1
fi

sudo cephadm ls | python3 -B -c '
import json, sys
if json.load(sys.stdin) != []:
    raise SystemExit("existing Ceph daemons")
'

mkdir -m 0700 "$root_dir/bootstrap-01"
cd "$root_dir/bootstrap-01"

cat > initial-ceph.conf <<'EOF'
[global]
public_network = 10.77.0.0/24
auth_cluster_required = cephx
auth_service_required = cephx
auth_client_required = cephx
ms_bind_ipv4 = true
ms_bind_ipv6 = false
osd_crush_chooseleaf_type = 1
osd_pool_default_size = 3
osd_pool_default_min_size = 0

[mon]
auth_allow_insecure_global_id_reclaim = false
mon_allow_pool_size_one = false

[osd]
osd_memory_target_autotune = false
osd_memory_target = 3221225472
EOF

fsid=$(cat /proc/sys/kernel/random/uuid)
printf '%s\n' "$fsid" > fsid.planned.txt
printf '%s\n' "$image" > ceph-image.txt
sha256sum initial-ceph.conf fsid.planned.txt ceph-image.txt > SHA256SUMS.inputs
printf 'status=attempted\nfsid=%s\n' "$fsid" > BOOTSTRAP-ATTEMPTED.txt

sudo cephadm --image "$image" bootstrap \
  --fsid "$fsid" --mon-ip 10.77.0.11 --ssh-user cephops \
  --ssh-private-key "$access/orchestrator_ed25519" \
  --ssh-public-key "$access/orchestrator_ed25519.pub" \
  --config "$PWD/initial-ceph.conf" --skip-dashboard \
  --skip-monitoring-stack --no-cleanup-on-failure \
  > bootstrap.stdout.txt 2> bootstrap.stderr.txt

c() {
  sudo cephadm --image "$image" shell --fsid "$fsid" -- ceph "$@"
}

c fsid > fsid.observed.txt
test "$(cat fsid.observed.txt)" = "$fsid"

c orch apply mon --placement="1 ceph1"
c orch apply mgr --placement="1 ceph1"

c quorum_status --format=json > quorum.json
c mgr dump --format=json > mgr.json
python3 -B - <<'PY'
import json

q, m = (json.load(open(p)) for p in ("quorum.json", "mgr.json"))
if q.get("quorum_names") != ["ceph1"]:
    raise SystemExit("unexpected MON quorum")
if not m.get("available") or not m.get("active_name"):
    raise SystemExit("no active manager")
PY

c status --format=json > status.json
sha256sum SHA256SUMS.inputs fsid.observed.txt quorum.json mgr.json status.json \
  > SHA256SUMS.bootstrap
printf 'status=accepted-bootstrap\nfsid=%s\n' "$fsid" > BOOTSTRAP-ACCEPTED.txt
