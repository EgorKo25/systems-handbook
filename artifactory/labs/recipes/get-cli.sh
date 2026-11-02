#!/usr/bin/env bash
# Linux amd64 only. Own tools directory; never changes PATH or installs packages.
set -euo pipefail
target_dir=${1:?usage: bash recipes/get-cli.sh OWN_NEW_TOOLS_DIRECTORY}
mkdir -p -- "$target_dir"
target_dir=$(cd -- "$target_dir" && pwd)
test ! -e "$target_dir/jf" || { printf '%s\n' 'Refusing to replace existing jf' >&2; exit 1; }
temporary=$(mktemp "$target_dir/.jf-download.XXXXXXXX")
trap 'rm -f -- "$temporary"' EXIT
"${AFT_CURL_BIN:-curl}" --fail --location --output "$temporary" \
  https://releases.jfrog.io/artifactory/jfrog-cli/v2-jf/2.129.0/jfrog-cli-linux-amd64/jf
printf '%s  %s\n' 8aaa3d46934e23a75c23a209780d95508199cddb5398b88e1c179cc86024a314 "$temporary" | sha256sum --check -
mv -- "$temporary" "$target_dir/jf"
chmod u+x -- "$target_dir/jf"
"$target_dir/jf" --version
