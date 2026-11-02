#!/usr/bin/env bash
# Read-only. Invoked as a separate process; never source into an interactive shell.
set -euo pipefail
: "${LAB_KUBECONFIG:?Set own existing kubeconfig}"
: "${LAB_CONTEXT:?Set own explicit context}"
[[ -f "$LAB_KUBECONFIG" ]] || { echo 'Kubeconfig does not exist' >&2; exit 1; }
kubectl --kubeconfig "$LAB_KUBECONFIG" --context "$LAB_CONTEXT" version
for resource in customresourcedefinitions.apiextensions.k8s.io clusterroles.rbac.authorization.k8s.io clusterrolebindings.rbac.authorization.k8s.io namespaces; do
  kubectl --kubeconfig "$LAB_KUBECONFIG" --context "$LAB_CONTEXT" auth can-i create "$resource" --quiet || { echo "Missing create permission: $resource" >&2; exit 1; }
done
kubectl --kubeconfig "$LAB_KUBECONFIG" --context "$LAB_CONTEXT" auth can-i get secrets -n argocd --quiet || { echo 'Cannot read Argo configuration in personal lab' >&2; exit 1; }
echo 'Preflight passed for the explicitly selected cluster; no mutations performed.'
