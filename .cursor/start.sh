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
  if [ -n "${ANTHROPIC_API_KEY:-}" ]; then
    sed -i "s|^ANTHROPIC_API_KEY=.*|ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}|" "$REPO_ROOT/.env"
  fi
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
