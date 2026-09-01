#!/usr/bin/env bash
# ============================================================================
# OpenSRE — Cloud Agent start script (runs on every boot)
# ============================================================================
# Per-boot responsibilities only:
#   1. Make sure the Docker daemon is running (with the nested-networking fix).
#   2. Bring the whole OpenSRE stack up via `make dev` (docker compose up -d).
#
# Heavy, one-time work (installing Docker, building images, creating volumes)
# lives in install.sh so it is captured in the environment snapshot and NOT
# repeated here. This script must tolerate restarts and reach a clear success.
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$REPO_ROOT"

echo "[start] Booting OpenSRE dev stack from $REPO_ROOT"

# 1. Ensure the Docker daemon is up and the networking fix is applied.
"$SCRIPT_DIR/start-dockerd.sh"

# 2. Safety net: if a previous boot / another checkout left the .env missing
#    (it is git-ignored), recreate it so `make dev` can read it.
if [ ! -f "$REPO_ROOT/.env" ]; then
  echo "[start] .env missing — recreating from .env.example"
  cp "$REPO_ROOT/.env.example" "$REPO_ROOT/.env"
fi

# Always sync the ANTHROPIC_API_KEY from the environment (Cloud Agent secret)
# into .env on every boot. This runs even when .env already exists, so applying
# the secret and restarting is enough to pick it up — no manual edit needed.
if [ -n "${ANTHROPIC_API_KEY:-}" ]; then
  echo "[start] Syncing ANTHROPIC_API_KEY from the environment into .env"
  sed -i "s|^ANTHROPIC_API_KEY=.*|ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}|" "$REPO_ROOT/.env"
fi

# Point the sre-agent at a reachable Anthropic IP.
# docker-compose.yml pins api.anthropic.com to a Cloudflare edge IP as an India
# TLS workaround, but that edge is unreachable from Cloud Agent VMs, which makes
# every LLM call hang. We resolve Anthropic's real IPv4 on the host (no /etc/hosts
# pin here) and pass it to compose via ANTHROPIC_HOST_IP so the container uses a
# route that actually works. Falls back to Anthropic's canonical IP if resolution
# fails. This does not change the committed default for other networks.
ANTHROPIC_HOST_IP="$(python3 -c "import socket; print(sorted({a[4][0] for a in socket.getaddrinfo('api.anthropic.com',443,socket.AF_INET)})[0])" 2>/dev/null || true)"
ANTHROPIC_HOST_IP="${ANTHROPIC_HOST_IP:-160.79.104.10}"
echo "[start] Using ANTHROPIC_HOST_IP=${ANTHROPIC_HOST_IP} for the sre-agent"
if grep -q '^ANTHROPIC_HOST_IP=' "$REPO_ROOT/.env"; then
  sed -i "s|^ANTHROPIC_HOST_IP=.*|ANTHROPIC_HOST_IP=${ANTHROPIC_HOST_IP}|" "$REPO_ROOT/.env"
else
  echo "ANTHROPIC_HOST_IP=${ANTHROPIC_HOST_IP}" >> "$REPO_ROOT/.env"
fi

# 3. The compose volumes are external, so make sure they exist (idempotent).
for vol in opensre-postgres-data opensre-neo4j-data opensre-agent-sessions; do
  docker volume create "$vol" >/dev/null
done

# 4. Bring the stack up. COMPOSE_PROJECT_NAME=opensre matches the fixed
#    container names in docker-compose.yml. `make dev` runs the LLM-config
#    helper, reconciles stale containers, then `docker compose up -d --build`.
#    It is idempotent: already-running services are left in place.
export COMPOSE_PROJECT_NAME=opensre
echo "[start] Starting services (postgres, config-service, neo4j, sre-agent, web-ui)..."
make dev

echo "[start] OpenSRE is up. Web console: http://localhost:3002 (admin token: local-admin-token)"
