#!/usr/bin/env bash
set -euo pipefail

# ─────────────────────────────────────────────────────────────────
# OpenSRE E2E — EKS cluster setup
# Installs otel-demo on an existing EKS cluster.
# Unlike kind, no image pre-loading or NodePort hacks needed.
# ─────────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BASE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT_ROOT="$(cd "$BASE_DIR/.." && pwd)"
source "$PROJECT_ROOT/scripts/banner.sh"

EKS_CLUSTER="${EKS_CLUSTER:?ERROR: EKS_CLUSTER env var is required (e.g. export EKS_CLUSTER=my-cluster)}"
EKS_REGION="${EKS_REGION:?ERROR: EKS_REGION env var is required (e.g. export EKS_REGION=us-west-2)}"
OTEL_NAMESPACE="${OTEL_NAMESPACE:-otel-demo}"
OTEL_CHART_VER="${OTEL_CHART_VER:-0.32.8}"

print_banner
echo ""
echo " EKS E2E Setup"
echo "  Cluster:   $EKS_CLUSTER"
echo "  Region:    $EKS_REGION"
echo "  Namespace: $OTEL_NAMESPACE"
echo ""

# ── 1. Ensure kubeconfig is set up ──
echo "[eks-setup] Verifying kubectl access to EKS cluster..."
# Try aws eks update-kubeconfig if available, otherwise assume kubectl is already configured
if command -v aws &>/dev/null; then
    aws eks update-kubeconfig --name "$EKS_CLUSTER" --region "$EKS_REGION" 2>/dev/null || true
fi
kubectl cluster-info 2>/dev/null | head -1

# ── 2. Verify connectivity ──
echo "[eks-setup] Verifying cluster access..."
NODE_COUNT=$(kubectl get nodes --no-headers 2>/dev/null | wc -l | tr -d ' ')
echo "  $NODE_COUNT nodes ready"
if [ "$NODE_COUNT" -lt 1 ]; then
    echo "ERROR: No nodes found. Check EKS cluster status."
    exit 1
fi

# ── 3. Install otel-demo via Helm ──
echo "[eks-setup] Installing otel-demo (chart v$OTEL_CHART_VER)..."
helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts 2>/dev/null || true
helm repo update open-telemetry > /dev/null 2>&1
kubectl create namespace "$OTEL_NAMESPACE" 2>/dev/null || true

if helm status otel-demo -n "$OTEL_NAMESPACE" > /dev/null 2>&1; then
    echo "  otel-demo already installed, upgrading..."
    helm upgrade otel-demo open-telemetry/opentelemetry-demo \
        --version "$OTEL_CHART_VER" -n "$OTEL_NAMESPACE" \
        -f "$BASE_DIR/otel-demo-values-base.yaml" \
        -f "$SCRIPT_DIR/otel-demo-values-eks.yaml"
else
    helm install otel-demo open-telemetry/opentelemetry-demo \
        --version "$OTEL_CHART_VER" -n "$OTEL_NAMESPACE" \
        -f "$BASE_DIR/otel-demo-values-base.yaml" \
        -f "$SCRIPT_DIR/otel-demo-values-eks.yaml"
fi

# ── 4. Wait for pods ──
echo "[eks-setup] Waiting for otel-demo pods (timeout 5m)..."
for i in $(seq 1 30); do
    READY=$(kubectl get pods -n "$OTEL_NAMESPACE" --no-headers 2>/dev/null \
        | awk '{print $3}' | grep -c Running || echo 0)
    TOTAL=$(kubectl get pods -n "$OTEL_NAMESPACE" --no-headers 2>/dev/null \
        | wc -l | tr -d ' ')
    echo "  $READY/$TOTAL running (${i}0s)"
    if [ "$READY" -ge 22 ]; then echo "  All pods ready!"; break; fi
    if [ "$i" -eq 30 ]; then
        echo "  WARNING: Timeout — some pods not ready:"
        kubectl get pods -n "$OTEL_NAMESPACE" --no-headers | grep -v Running
    fi
    sleep 10
done

# ── 5. Start port-forward tunnels from host ──
echo "[eks-setup] Starting port-forward tunnels..."
bash "$SCRIPT_DIR/port-forward.sh" start

echo ""
print_banner
echo ""
echo " EKS E2E Setup Complete!"
echo "  Prometheus:    http://localhost:9090"
echo "  Grafana:       http://localhost:3000"
echo "  Jaeger:        http://localhost:16686"
echo "  OpenSearch:    http://localhost:9200"
echo "  otel Frontend: http://localhost:8090"
echo ""
echo "Run 'make e2e-test' to trigger a cart failure investigation."
