#!/usr/bin/env bash
# UNEXECUTED recipe for administrator of their OWN NEW personal Linux VM only.
# Creates a service identity and /opt/jfrog; never use on the workstation.
set -euo pipefail
archive=${1:?usage: bash recipes/extract-vm.sh VERIFIED_SERVER_ARCHIVE}
test -f "$archive"
printf '%s  %s\n' 0a69e185392441a8e7d3c705b15ae2083e289eff4039d139ece1d3e02888699e "$archive" | sha256sum --check -
# This guard runs before any extraction or sudo command.
test ! -e /opt/jfrog/artifactory || { printf '%s\n' 'Existing installation; this is not an upgrade script' >&2; exit 1; }
if id artifactory >/dev/null 2>&1; then
  printf '%s\n' 'Existing service identity; inspect ownership before proceeding' >&2
  exit 1
fi
listing=$(mktemp)
trap 'rm -f -- "$listing"' EXIT
tar -tzf "$archive" > "$listing"
sed -n '1,12p' "$listing"
grep -q '^artifactory-pro-7\.161\.20/' "$listing"
sudo useradd --system --home-dir /opt/jfrog --shell /usr/sbin/nologin artifactory
sudo install -d -o artifactory -g artifactory -m0750 /opt/jfrog
sudo tar -xzf "$archive" -C /opt/jfrog
test -d /opt/jfrog/artifactory-pro-7.161.20/app
sudo mv /opt/jfrog/artifactory-pro-7.161.20 /opt/jfrog/artifactory
sudo chown -R artifactory:artifactory /opt/jfrog/artifactory
printf '%s\n' 'Extracted only. Configure private system.yaml and database before start.'
