#!/usr/bin/env bash
set -euo pipefail

# ─────────────────────────────────────────────────────────────────
# OpenSRE E2E — Port-forward tunnels for EKS
# Starts/stops kubectl port-forward tunnels from the host to EKS
# services. These make observability tools available on localhost.
# ─────────────────────────────────────────────────────────────────

OTEL_NAMESPACE="${OTEL_NAMESPACE:-otel-demo}"
PID_DIR="${PID_DIR:-/tmp/opensre-e2e-pf}"

TUNNELS=(
    "otel-demo-prometheus-server 9090 9090 Prometheus"
    "otel-demo-grafana 3000 80 Grafana"
    "otel-demo-jaeger-query 16686 16686 Jaeger"
    "otel-demo-opensearch 9200 9200 OpenSearch"
    "otel-demo-frontendproxy 8090 8080 Frontend"
)

check_port() {
    local port=$1
    python3 -c "import socket; s=socket.socket(); s.settimeout(2); s.connect(('127.0.0.1',$port)); s.close()" 2>/dev/null
}

start_tunnels() {
    mkdir -p "$PID_DIR"
    echo "[port-forward] Starting tunnels to namespace=$OTEL_NAMESPACE..."

    for tunnel in "${TUNNELS[@]}"; do
        read -r svc local_port remote_port name <<< "$tunnel"

        # Kill any existing tunnel on this port
        if [ -f "$PID_DIR/$name.pid" ]; then
            kill "$(cat "$PID_DIR/$name.pid")" 2>/dev/null || true
            rm -f "$PID_DIR/$name.pid"
        fi

        kubectl port-forward "svc/$svc" -n "$OTEL_NAMESPACE" \
            "${local_port}:${remote_port}" --address=127.0.0.1 &
        echo $! > "$PID_DIR/$name.pid"
    done

    # Wait for tunnels to be ready
    echo "[port-forward] Waiting for tunnels..."
    for tunnel in "${TUNNELS[@]}"; do
        read -r svc local_port remote_port name <<< "$tunnel"
        local start
        start=$(date +%s)
        while ! check_port "$local_port"; do
            if [ $(($(date +%s) - start)) -ge 30 ]; then
                echo "  WARN: $name on port $local_port not ready after 30s"
                break
            fi
            sleep 1
        done
        if check_port "$local_port"; then
            echo "  OK: $name on port $local_port"
        fi
    done
}

stop_tunnels() {
    echo "[port-forward] Stopping tunnels..."
    if [ -d "$PID_DIR" ]; then
        for pidfile in "$PID_DIR"/*.pid; do
            [ -f "$pidfile" ] || continue
            kill "$(cat "$pidfile")" 2>/dev/null || true
            rm -f "$pidfile"
        done
        rmdir "$PID_DIR" 2>/dev/null || true
    fi
    # Also kill any stray port-forwards for otel-demo
    pkill -f "port-forward.*otel-demo" 2>/dev/null || true
    echo "[port-forward] All tunnels stopped."
}

status_tunnels() {
    for tunnel in "${TUNNELS[@]}"; do
        read -r svc local_port remote_port name <<< "$tunnel"
        if check_port "$local_port"; then
            echo "  OK: $name on port $local_port"
        else
            echo "  DOWN: $name on port $local_port"
        fi
    done
}

case "${1:-status}" in
    start)   start_tunnels ;;
    stop)    stop_tunnels ;;
    status)  status_tunnels ;;
    *)       echo "Usage: $0 {start|stop|status}"; exit 1 ;;
esac
