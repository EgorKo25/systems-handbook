#!/usr/bin/env bash
# Only the console of a personally owned Ubuntu 22.04 amd64 VM.
set -euo pipefail
umask 077
set -o noclobber

systemd-detect-virt --vm >/dev/null
expected_host=${1:?expected ceph1, ceph2, ceph3 or ceph4}
case "$expected_host" in ceph1|ceph2|ceph3|ceph4) ;; *) exit 2 ;; esac
test "$(hostname -s)" = "$expected_host"
expected_image=${2:-}
if [[ "$expected_host" != ceph1 ]]; then
  [[ "$expected_image" =~ ^quay\.io/ceph/ceph@sha256:[0-9a-f]{64}$ ]]
fi
test "$(dpkg --print-architecture)" = amd64
. /etc/os-release
test "$ID" = ubuntu
test "$VERSION_ID" = 22.04

root_dir="$HOME/ceph-study"
test -d "$root_dir"
test ! -L "$root_dir"
test "$(stat -c %u "$root_dir")" = "$(id -u)"
test "$(stat -c %a "$root_dir")" = 700

supply="$root_dir/supply-20.2.4-01"
test -d "$supply"
test ! -L "$supply"
test "$(stat -c %u "$supply")" = "$(id -u)"
(
  cd "$supply"
  test "$(sed -n 's/^status=//p' SIGNATURE-ACCEPTED.txt)" = accepted-signature-inputs
  sha256sum -c SHA256SUMS.signature
)

mkdir -m 0700 "$root_dir/runtime-20.2.4-01"
cd "$root_dir/runtime-20.2.4-01"

cat "$supply/ceph-release.gpg" > ceph-release.gpg
cat > ceph-study-20.2.4.list <<'EOF'
deb [arch=amd64 signed-by=/usr/share/keyrings/ceph-study-20.2.4.gpg] https://download.ceph.com/debian-20.2.4/ jammy main
EOF

publish_root_file() {
  local src="$1" dst="$2"
  if sudo test -L "$dst"; then
    return 1
  fi
  if sudo test -e "$dst"; then
    sudo test -f "$dst"
    sudo cmp --silent "$src" "$dst"
  else
    sudo bash --noprofile --norc -c '
      set -euo pipefail
      set -o noclobber
      umask 022
      cat > "$1"
      chmod 0644 "$1"
    ' bash "$dst" < "$src"
  fi
}

publish_root_file "$PWD/ceph-release.gpg" \
  /usr/share/keyrings/ceph-study-20.2.4.gpg
publish_root_file "$PWD/ceph-study-20.2.4.list" \
  /etc/apt/sources.list.d/ceph-study-20.2.4.list

sudo apt-get update > apt-update.stdout.txt 2> apt-update.stderr.txt
LC_ALL=C apt-cache policy cephadm > cephadm-policy.txt
LC_ALL=C apt-cache madison cephadm > cephadm-origins.txt
candidate=$(awk '$1=="Candidate:" {print $2}' cephadm-policy.txt)

python3 -B - "$candidate" <<'PY'
import pathlib, re, sys

candidate = sys.argv[1]
if not re.fullmatch(r"(?:[0-9]+:)?20\.2\.4[-+][A-Za-z0-9.+:~\-]+", candidate):
    raise SystemExit("cephadm candidate is not upstream 20.2.4")

rows = [
    line.split("|")
    for line in pathlib.Path("cephadm-origins.txt").read_text().splitlines()
]
origins = [
    row[2].strip()
    for row in rows
    if len(row) == 3 and row[1].strip() == candidate
]
prefix = "https://download.ceph.com/debian-20.2.4"
if not origins or not all(o.split()[0].rstrip("/") == prefix for o in origins):
    raise SystemExit("ambiguous or unexpected package origin")
PY

if dpkg-query -W -f='${Version}\n' cephadm \
    > cephadm-before.txt 2> cephadm-before.stderr.txt; then
  test "$(cat cephadm-before.txt)" = "$candidate"
fi

printf '%s\n' "$candidate" > cephadm-package.expected.txt
sudo apt-get install --yes --no-install-recommends "cephadm=$candidate" podman \
  > apt-install.stdout.txt 2> apt-install.stderr.txt

dpkg-query -W -f='${Version}\n' cephadm > cephadm-package.observed.txt
test "$(cat cephadm-package.observed.txt)" = "$candidate"

sudo cephadm version --verbose > cephadm-version.json
python3 -B - <<'PY'
import json
v = json.load(open("cephadm-version.json"))
if v.get("ceph_git_nice_ver") not in {"20.2.4", "v20.2.4"}:
    raise SystemExit("cephadm native version mismatch")
PY

tag=quay.io/ceph/ceph:v20.2.4
sudo podman pull "$tag" > image-pull.stdout.txt 2> image-pull.stderr.txt
sudo podman image inspect "$tag" > podman-image.json

python3 -B - <<'PY' > ceph-image.txt
import json, re

data = json.load(open("podman-image.json"))
if len(data) != 1 or data[0].get("Architecture") != "amd64":
    raise SystemExit("image architecture mismatch")
digests = sorted(
    d for d in data[0].get("RepoDigests", [])
    if re.fullmatch(r"quay\.io/ceph/ceph@sha256:[0-9a-f]{64}", d)
)
if not digests:
    raise SystemExit("no immutable repository digest")
print(digests[0])
PY

image=$(cat ceph-image.txt)
if [[ -n "$expected_image" ]]; then test "$image" = "$expected_image"; fi
sudo podman pull "$image" > digest-pull.stdout.txt 2> digest-pull.stderr.txt
sudo cephadm --image "$image" inspect-image > ceph-image.inspect.json

python3 -B - "$image" <<'PY'
import json, sys

data = json.load(open("ceph-image.inspect.json"))
if not data.get("ceph_version", "").startswith("ceph version 20.2.4 "):
    raise SystemExit("image native version mismatch")
if sys.argv[1] not in data.get("repo_digests", []):
    raise SystemExit("inspected image does not expose accepted digest")
PY

cat /etc/os-release > host-os-release.txt
uname -r > host-kernel-release.txt
sudo podman --version > podman-version.txt

sha256sum ceph-release.gpg ceph-study-20.2.4.list \
  host-os-release.txt host-kernel-release.txt podman-version.txt \
  cephadm-policy.txt cephadm-origins.txt \
  cephadm-package.expected.txt cephadm-package.observed.txt \
  cephadm-version.json podman-image.json ceph-image.txt ceph-image.inspect.json \
  > SHA256SUMS.runtime

printf 'status=accepted-runtime\nversion=20.2.4\nimage=%s\n' "$image" \
  > RUNTIME-ACCEPTED.txt
