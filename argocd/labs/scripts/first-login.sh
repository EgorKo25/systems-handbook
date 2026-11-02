#!/usr/bin/env bash
# One-time first-login recipe; keep a separately opened loopback port-forward running.
set -euo pipefail
: "${LAB_KUBECONFIG:?Set own kubeconfig}"
: "${LAB_CONTEXT:?Set explicit context}"
: "${LAB_ROOT:?Set persistent lab directory}"
: "${ARGOCD_BIN:?Set verified Argo CD executable}"
[[ -f "$LAB_KUBECONFIG" && -x "$ARGOCD_BIN" ]] || { echo 'Missing explicit inputs' >&2; exit 1; }
umask 077
mkdir -p "$LAB_ROOT/private"
kubectl --kubeconfig "$LAB_KUBECONFIG" --context "$LAB_CONTEXT" -n argocd rollout status deployment/argocd-server --timeout=60s
kubectl --kubeconfig "$LAB_KUBECONFIG" --context "$LAB_CONTEXT" -n argocd get secret argocd-secret -o jsonpath='{.data.tls\.crt}' | base64 --decode > "$LAB_ROOT/private/server.crt"
[[ -s "$LAB_ROOT/private/server.crt" ]] || { echo 'No certificate; inspect configured argocd-server-tls/argocd-secret owner' >&2; exit 1; }
openssl x509 -in "$LAB_ROOT/private/server.crt" -noout -subject -issuer -dates -ext subjectAltName
openssl verify -CAfile "$LAB_ROOT/private/server.crt" -verify_hostname localhost "$LAB_ROOT/private/server.crt"
"$ARGOCD_BIN" admin initial-password --kubeconfig "$LAB_KUBECONFIG" --context "$LAB_CONTEXT" --namespace argocd
"$ARGOCD_BIN" --config "$LAB_ROOT/private/argocd-config" --server-crt "$LAB_ROOT/private/server.crt" login localhost:8443 --username admin --name handbook
"$ARGOCD_BIN" --config "$LAB_ROOT/private/argocd-config" --argocd-context handbook account update-password
echo 'First login/password change succeeded. Keep client config private.'
