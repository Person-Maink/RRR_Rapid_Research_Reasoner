#!/usr/bin/env bash
set -euo pipefail

NAMESPACE="${NAMESPACE:-rrr}"
RELEASE="${RELEASE:-rrr}"
CHART="${CHART:-infra/helm/rrr}"
VALUES="${VALUES:-infra/helm/rrr/values-minikube.yaml}"

helm upgrade --install "$RELEASE" "$CHART" \
  --namespace "$NAMESPACE" \
  --create-namespace \
  -f "$VALUES"

kubectl rollout status "deployment/${RELEASE}-rrr-api" -n "$NAMESPACE" --timeout=180s
kubectl rollout status "deployment/${RELEASE}-rrr-frontend" -n "$NAMESPACE" --timeout=180s

kubectl port-forward "svc/${RELEASE}-rrr-api" 18000:8000 -n "$NAMESPACE" >/tmp/rrr-api-port-forward.log 2>&1 &
PORT_FORWARD_PID=$!
trap 'kill "$PORT_FORWARD_PID" >/dev/null 2>&1 || true' EXIT

sleep 3
curl --fail http://localhost:18000/healthz
echo "Minikube smoke check passed."
