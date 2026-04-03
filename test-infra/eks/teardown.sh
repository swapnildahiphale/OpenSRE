#!/usr/bin/env bash
set -euo pipefail

# ─────────────────────────────────────────────────────────────────
# OpenSRE E2E — EKS teardown
# Uninstalls otel-demo from EKS and stops port-forward tunnels.
# Does NOT delete the EKS cluster itself.
# ─────────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OTEL_NAMESPACE="${OTEL_NAMESPACE:-otel-demo}"

echo "[eks-teardown] Stopping port-forward tunnels..."
bash "$SCRIPT_DIR/port-forward.sh" stop

echo "[eks-teardown] Uninstalling otel-demo from namespace '$OTEL_NAMESPACE'..."
helm uninstall otel-demo -n "$OTEL_NAMESPACE" 2>/dev/null || echo "  otel-demo not installed"

echo "[eks-teardown] Deleting namespace '$OTEL_NAMESPACE'..."
kubectl delete namespace "$OTEL_NAMESPACE" --ignore-not-found 2>/dev/null || true

echo "[eks-teardown] Done."
