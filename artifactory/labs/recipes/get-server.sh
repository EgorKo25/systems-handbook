#!/usr/bin/env bash
# Personal download folder only. Does not extract or start the server.
set -euo pipefail
target_dir=${1:?usage: bash recipes/get-server.sh OWN_DOWNLOAD_DIRECTORY}
mkdir -p -- "$target_dir"
target_dir=$(cd -- "$target_dir" && pwd)
name=jfrog-artifactory-pro-7.161.20-linux.tar.gz
test ! -e "$target_dir/$name" || { printf '%s\n' 'Refusing to replace existing archive' >&2; exit 1; }
temporary=$(mktemp "$target_dir/.server-download.XXXXXXXX")
trap 'rm -f -- "$temporary"' EXIT
"${AFT_CURL_BIN:-curl}" --fail --location --output "$temporary" \
  https://releases.jfrog.io/artifactory/artifactory-pro/org/artifactory/pro/jfrog-artifactory-pro/7.161.20/jfrog-artifactory-pro-7.161.20-linux.tar.gz
printf '%s  %s\n' 0a69e185392441a8e7d3c705b15ae2083e289eff4039d139ece1d3e02888699e "$temporary" | sha256sum --check -
mv -- "$temporary" "$target_dir/$name"
printf '%s\n' 'Verified archive. Server is not installed or started.'
