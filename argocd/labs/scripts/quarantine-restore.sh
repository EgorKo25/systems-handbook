#!/usr/bin/env bash
# Only quarantine a separately prepared PERSONAL restore target. Never import/resume.
set -euo pipefail
: "${RESTORE_KUBECONFIG:?Set separately prepared restore kubeconfig}"
: "${RESTORE_CONTEXT:?Set explicitly new restore context}"
: "${RESTORE_EXPECTED_SERVER:?Set independently verified restore API endpoint}"
: "${RESTORE_EXPECTED_CLUSTER_UID:?Record new kube-system UID before this procedure}"
[[ -f "$RESTORE_KUBECONFIG" ]] || { echo 'Missing explicit kubeconfig' >&2; exit 1; }
new_server=$(kubectl --kubeconfig "$RESTORE_KUBECONFIG" --context "$RESTORE_CONTEXT" config view --minify -o jsonpath='{.clusters[0].cluster.server}')
[[ "$new_server" == "$RESTORE_EXPECTED_SERVER" ]] || { echo 'Restore endpoint mismatch' >&2; exit 1; }
if [[ -n "${SOURCE_CLUSTER_UID:-}" ]]; then
  old_uid="$SOURCE_CLUSTER_UID" # independently recorded before the outage, never guessed
else
  : "${LAB_KUBECONFIG:?Set original kubeconfig or independently recorded SOURCE_CLUSTER_UID}"
  : "${LAB_CONTEXT:?Set original context}"
  [[ -f "$LAB_KUBECONFIG" ]] || { echo 'Missing original kubeconfig' >&2; exit 1; }
  old_uid=$(kubectl --kubeconfig "$LAB_KUBECONFIG" --context "$LAB_CONTEXT" get namespace kube-system -o jsonpath='{.metadata.uid}')
fi
new_uid=$(kubectl --kubeconfig "$RESTORE_KUBECONFIG" --context "$RESTORE_CONTEXT" get namespace kube-system -o jsonpath='{.metadata.uid}')
[[ -n "$old_uid" && -n "$new_uid" && "$new_uid" == "$RESTORE_EXPECTED_CLUSTER_UID" && "$new_uid" != "$old_uid" ]] || { echo 'Restore target must be a different independently identified cluster' >&2; exit 1; }
marker=$(kubectl --kubeconfig "$RESTORE_KUBECONFIG" --context "$RESTORE_CONTEXT" get namespace argocd -o jsonpath='{.metadata.labels.handbook\.example/restore}')
[[ "$marker" == quarantine ]] || { echo 'Restore namespace has not been explicitly marked quarantine by its owner' >&2; exit 1; }
kubectl --kubeconfig "$RESTORE_KUBECONFIG" --context "$RESTORE_CONTEXT" -n argocd scale deployment/argocd-notifications-controller --replicas=0
kubectl --kubeconfig "$RESTORE_KUBECONFIG" --context "$RESTORE_CONTEXT" -n argocd scale deployment/argocd-applicationset-controller --replicas=0
kubectl --kubeconfig "$RESTORE_KUBECONFIG" --context "$RESTORE_CONTEXT" -n argocd scale statefulset/argocd-application-controller --replicas=0
stopped=false
for attempt in {1..60}; do
  count=$(kubectl --kubeconfig "$RESTORE_KUBECONFIG" --context "$RESTORE_CONTEXT" -n argocd get pods -l 'app.kubernetes.io/name in (argocd-application-controller,argocd-applicationset-controller,argocd-notifications-controller)' -o json | python3 -c 'import json,sys; print(len(json.load(sys.stdin)["items"]))')
  if [[ "$count" == 0 ]]; then stopped=true; break; fi
  sleep 1
done
[[ "$stopped" == true ]] || { echo 'Controller Pods still present; no import allowed' >&2; exit 1; }
echo 'Quarantine checked:three controllers have zero Pods. Import/review/resume remain separate owner actions.'
