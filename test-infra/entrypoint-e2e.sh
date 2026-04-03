#!/usr/bin/env bash
set -euo pipefail

# ─────────────────────────────────────────────────────────────────
# OpenSRE E2E Entrypoint
# Starts kubectl port-forward tunnels for observability tools,
# monitors them with a background watchdog, then execs the server.
# ─────────────────────────────────────────────────────────────────

NAMESPACE="${OTEL_NAMESPACE:-otel-demo}"

# Tunnel definitions: svc_name local_port remote_port display_name
TUNNELS=(
    "otel-demo-prometheus-server 9090 9090 Prometheus"
    "otel-demo-grafana 3000 80 Grafana"
    "otel-demo-jaeger-query 16686 16686 Jaeger"
    "otel-demo-opensearch 9200 9200 OpenSearch"
)

check_port() {
    local port=$1
    python3 -c "import socket; s=socket.socket(); s.settimeout(2); s.connect(('127.0.0.1',$port)); s.close()" 2>/dev/null
}

start_tunnel() {
    local svc=$1 local_port=$2 remote_port=$3 name=$4
    kubectl port-forward "svc/$svc" -n "$NAMESPACE" "${local_port}:${remote_port}" --address=0.0.0.0 &
}

wait_for_port() {
    local port=$1 name=$2 max_wait=${3:-30}
    local start
    start=$(date +%s)
    while ! check_port "$port"; do
        if [ $(($(date +%s) - start)) -ge "$max_wait" ]; then
            echo "[e2e-entrypoint] WARN: $name on port $port not ready after ${max_wait}s"
            return 1
        fi
        sleep 1
    done
    echo "[e2e-entrypoint] OK: $name ready on port $port"
}

check_and_restart_tunnel() {
    local svc=$1 local_port=$2 remote_port=$3 name=$4
    if ! check_port "$local_port"; then
        echo "[e2e-entrypoint] WARN: $name tunnel died, restarting..."
        pkill -f "port-forward.*${svc}" 2>/dev/null || true
        sleep 1
        start_tunnel "$svc" "$local_port" "$remote_port" "$name"
    fi
}

monitor_tunnels() {
    while true; do
        sleep 30
        for tunnel in "${TUNNELS[@]}"; do
            read -r svc local_port remote_port name <<< "$tunnel"
            check_and_restart_tunnel "$svc" "$local_port" "$remote_port" "$name"
        done
    done
}

# ── Start all tunnels ──
echo "[e2e-entrypoint] Starting observability tunnels to namespace=$NAMESPACE..."

for tunnel in "${TUNNELS[@]}"; do
    read -r svc local_port remote_port name <<< "$tunnel"
    start_tunnel "$svc" "$local_port" "$remote_port" "$name"
done

# ── Wait for all tunnels to become ready ──
for tunnel in "${TUNNELS[@]}"; do
    read -r svc local_port remote_port name <<< "$tunnel"
    wait_for_port "$local_port" "$name"
done

# ── Background watchdog: restart dead tunnels every 30s ──
monitor_tunnels &
echo "[e2e-entrypoint] Tunnel watchdog started (PID $!)"

echo "[e2e-entrypoint] All tunnels ready. Starting server..."
exec python server.py
