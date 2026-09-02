#!/usr/bin/env bash
# Ensure external Compose volumes exist before `make dev*`.
#
# Volumes are marked external:true in docker-compose.yml so
# `docker compose down -v` / `make clean` cannot wipe investigation data
# across worktrees. Compose will not create external volumes itself —
# create them once (idempotent) here.

set -euo pipefail

VOLUMES=(
  opensre-postgres-data
  opensre-neo4j-data
  opensre-agent-sessions
)

for name in "${VOLUMES[@]}"; do
  if docker volume inspect "$name" >/dev/null 2>&1; then
    continue
  fi
  echo "ensure-volumes: creating $name"
  docker volume create "$name" >/dev/null
done
