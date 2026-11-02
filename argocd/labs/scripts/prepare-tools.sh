#!/usr/bin/env bash
# Local tools only; verified fixed archives, no global PATH/system install.
set -euo pipefail
: "${LAB_ROOT:?Set persistent private lab directory}"
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
python3 "$SCRIPT_DIR/../prepare_bundle.py" --output "$LAB_ROOT/bundle" --verify-only
TARGET="$LAB_ROOT/tools/runtime-3.5.6"
[[ ! -e "$TARGET" ]] || { echo 'Runtime directory exists; keep it, inspect versions rather than overwriting' >&2; exit 1; }
mkdir -p "$LAB_ROOT/tools"
mkdir "$TARGET" "$TARGET/helm" "$TARGET/kustomize"
cp "$LAB_ROOT/bundle/argocd-linux-amd64" "$TARGET/argocd"
chmod 0755 "$TARGET/argocd"
tar -xzf "$LAB_ROOT/bundle/helm-v4.2.1-linux-amd64.tar.gz" -C "$TARGET/helm" linux-amd64/helm
tar -xzf "$LAB_ROOT/bundle/kustomize_v5.8.1_linux_amd64.tar.gz" -C "$TARGET/kustomize" kustomize
[[ "$("$TARGET/argocd" version --client --short)" == 'argocd: v3.5.6+c2b1e30' ]]
[[ "$("$TARGET/helm/linux-amd64/helm" version --short)" == v4.2.1+* ]]
[[ "$("$TARGET/kustomize/kustomize" version)" == 'v5.8.1' ]]
echo 'Pinned tools ready in reader-owned runtime-3.5.6; no global installation.'
