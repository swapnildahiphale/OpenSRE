#!/usr/bin/env bash
set -euo pipefail

# ─────────────────────────────────────────────────────────────────
# Generate a kubeconfig for sre-agent Docker container to reach EKS.
#
# The host kubeconfig uses `aws eks get-token` for auth, which
# requires AWS CLI inside the container. Instead, we generate a
# kubeconfig with a long-lived token from a ServiceAccount.
#
# Extracts cluster endpoint and CA from existing kubectl config
# (no AWS CLI needed if kubectl is already authenticated).
#
# For local E2E testing only — not for production use.
# ─────────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OUTPUT="$SCRIPT_DIR/kubeconfig-eks.yaml"

OTEL_NAMESPACE="${OTEL_NAMESPACE:-otel-demo}"
SA_NAME="opensre-e2e-agent"

echo "[eks-kubeconfig] Generating kubeconfig for sre-agent container..."

# ── 1. Get cluster endpoint and CA from current kubectl context ──
EKS_ENDPOINT=$(kubectl config view --minify --raw -o jsonpath='{.clusters[0].cluster.server}')
EKS_CA=$(kubectl config view --minify --raw -o jsonpath='{.clusters[0].cluster.certificate-authority-data}')
CLUSTER_NAME=$(kubectl config view --minify --raw -o jsonpath='{.clusters[0].name}')

echo "  Cluster: $CLUSTER_NAME"
echo "  Endpoint: $EKS_ENDPOINT"

if [ -z "$EKS_ENDPOINT" ] || [ -z "$EKS_CA" ]; then
    echo "ERROR: Could not extract cluster info from kubectl config."
    echo "  Ensure kubectl is configured and pointing at the right cluster."
    exit 1
fi

# ── 2. Create ServiceAccount + ClusterRoleBinding for E2E agent ──
kubectl apply -f - <<EOF
apiVersion: v1
kind: ServiceAccount
metadata:
  name: $SA_NAME
  namespace: $OTEL_NAMESPACE
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: opensre-e2e-agent-admin
subjects:
  - kind: ServiceAccount
    name: $SA_NAME
    namespace: $OTEL_NAMESPACE
roleRef:
  kind: ClusterRole
  name: cluster-admin
  apiGroup: rbac.authorization.k8s.io
EOF

# ── 3. Create a long-lived token secret ──
kubectl apply -f - <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: ${SA_NAME}-token
  namespace: $OTEL_NAMESPACE
  annotations:
    kubernetes.io/service-account.name: $SA_NAME
type: kubernetes.io/service-account-token
EOF

# Wait for token to be populated
echo "  Waiting for token..."
TOKEN=""
for i in $(seq 1 10); do
    TOKEN=$(kubectl get secret "${SA_NAME}-token" -n "$OTEL_NAMESPACE" \
        -o jsonpath='{.data.token}' 2>/dev/null | base64 -d 2>/dev/null || echo "")
    if [ -n "$TOKEN" ]; then break; fi
    sleep 2
done

if [ -z "$TOKEN" ]; then
    echo "ERROR: Failed to get ServiceAccount token after 20s"
    exit 1
fi

# ── 4. Write kubeconfig ──
cat > "$OUTPUT" <<EOF
apiVersion: v1
kind: Config
clusters:
  - cluster:
      server: $EKS_ENDPOINT
      certificate-authority-data: $EKS_CA
    name: $CLUSTER_NAME
contexts:
  - context:
      cluster: $CLUSTER_NAME
      user: $SA_NAME
      namespace: $OTEL_NAMESPACE
    name: $CLUSTER_NAME
current-context: $CLUSTER_NAME
users:
  - name: $SA_NAME
    user:
      token: $TOKEN
EOF

echo "[eks-kubeconfig] Written to $OUTPUT"
echo "  Context: $CLUSTER_NAME"
echo "  User: $SA_NAME (ServiceAccount token)"
