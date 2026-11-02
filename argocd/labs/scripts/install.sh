#!/usr/bin/env bash
# Owner-only recipe for an explicitly selected PERSONAL Kubernetes cluster.
set -euo pipefail
: "${LAB_ROOT:?Set persistent lab directory}"
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
LAB_FILES=$(cd -- "$SCRIPT_DIR/.." && pwd)
bash "$SCRIPT_DIR/preflight.sh"
python3 "$LAB_FILES/prepare_bundle.py" --output "$LAB_ROOT/bundle" --verify-only
work_dir=$(mktemp -d)
trap 'rm -rf -- "$work_dir"' EXIT
for ns in argocd gitops-lab; do
  kubectl --kubeconfig "$LAB_KUBECONFIG" --context "$LAB_CONTEXT" get namespace "$ns" --ignore-not-found -o json > "$work_dir/existing.json"
  if [[ -s "$work_dir/existing.json" ]]; then
    python3 - "$work_dir/existing.json" <<'PY'
import json,sys
obj=json.load(open(sys.argv[1]))
if obj.get('metadata',{}).get('labels',{}).get('handbook.example/owner')!='argocd-lab':
 raise SystemExit('Existing namespace has no matching reader-owned label; stop and establish ownership')
PY
  else
    python3 - "$ns" > "$work_dir/namespace.json" <<'PY'
import json,sys
print(json.dumps({'apiVersion':'v1','kind':'Namespace','metadata':{'name':sys.argv[1],'labels':{'handbook.example/owner':'argocd-lab'}}}))
PY
    kubectl --kubeconfig "$LAB_KUBECONFIG" --context "$LAB_CONTEXT" create -f "$work_dir/namespace.json"
  fi
done
kubectl --kubeconfig "$LAB_KUBECONFIG" --context "$LAB_CONTEXT" apply --server-side --dry-run=server -n argocd -f "$LAB_ROOT/bundle/install.yaml"
kubectl --kubeconfig "$LAB_KUBECONFIG" --context "$LAB_CONTEXT" apply --server-side -n argocd -f "$LAB_ROOT/bundle/install.yaml"
kubectl --kubeconfig "$LAB_KUBECONFIG" --context "$LAB_CONTEXT" wait --for=condition=Established crd/applications.argoproj.io crd/appprojects.argoproj.io crd/applicationsets.argoproj.io --timeout=120s
kubectl --kubeconfig "$LAB_KUBECONFIG" --context "$LAB_CONTEXT" -n argocd wait --for=condition=Available deployment --all --timeout=180s
kubectl --kubeconfig "$LAB_KUBECONFIG" --context "$LAB_CONTEXT" -n argocd rollout status statefulset/argocd-application-controller --timeout=180s
echo 'Install acceptance passed. Proceed to separately reviewed TLS/login steps.'
