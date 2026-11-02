#!/usr/bin/env bash
# Own NEW Linux amd64 tools folder. No daemon or global installation.
set -euo pipefail
directory=${1:?usage: bash recipes/get-oras.sh OWN_TOOLS_DIRECTORY}
mkdir -p -- "$directory"
directory=$(cd -- "$directory" && pwd)
test ! -e "$directory/oras" || { printf '%s\n' 'Refusing to replace oras' >&2; exit 1; }
temporary=$(mktemp "$directory/.oras-download.XXXXXXXX")
trap 'rm -f -- "$temporary"' EXIT
"${AFT_CURL_BIN:-curl}" --fail --location --output "$temporary" \
  https://github.com/oras-project/oras/releases/download/v1.3.6/oras_1.3.6_linux_amd64.tar.gz
printf '%s  %s\n' 66fb0ad7206f3f6fa77ed5b552049d364ccf4b50b1684554f731f76302b52ca0 "$temporary" | sha256sum --check -
tar -xzf "$temporary" -C "$directory" oras
chmod u+x -- "$directory/oras"
"$directory/oras" version
