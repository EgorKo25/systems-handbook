#!/usr/bin/env bash
# Apply only already reviewed reader-owned bootstrap files; no automatic sync.
set -euo pipefail
: "${LAB_KUBECONFIG:?Set own kubeconfig}"
: "${LAB_CONTEXT:?Set explicit context}"
: "${LAB_ROOT:?Set persistent lab directory}"
[[ -f "$LAB_KUBECONFIG" && -f "$LAB_ROOT/bootstrap-initial/project.yaml" && -f "$LAB_ROOT/bootstrap-initial/application.yaml" ]] || { echo 'Missing prepared files' >&2; exit 1; }
kubectl --kubeconfig "$LAB_KUBECONFIG" --context "$LAB_CONTEXT" -n argocd rollout status deployment/argocd-server --timeout=60s
kubectl --kubeconfig "$LAB_KUBECONFIG" --context "$LAB_CONTEXT" apply --dry-run=server -f "$LAB_ROOT/bootstrap-initial/project.yaml"
kubectl --kubeconfig "$LAB_KUBECONFIG" --context "$LAB_CONTEXT" apply -f "$LAB_ROOT/bootstrap-initial/project.yaml"
kubectl --kubeconfig "$LAB_KUBECONFIG" --context "$LAB_CONTEXT" apply --dry-run=server -f "$LAB_ROOT/bootstrap-initial/application.yaml"
kubectl --kubeconfig "$LAB_KUBECONFIG" --context "$LAB_CONTEXT" apply -f "$LAB_ROOT/bootstrap-initial/application.yaml"
echo 'Application created with automated.enabled=false; inspect source/diff before manual sync.'
