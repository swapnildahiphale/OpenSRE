#!/usr/bin/env bash
# Reconcile fixed-name OpenSRE containers across compose projects.
#
# docker-compose.yml sets container_name: opensre-* for stable local URLs/docs,
# but Compose otherwise derives the project name from the checkout directory.
# Parallel worktrees therefore fight over the same container names.
#
# Before `make dev*`, drop containers owned by a different compose project so
# the current checkout can recreate them under COMPOSE_PROJECT_NAME (default: opensre).

set -euo pipefail

PROJECT="${COMPOSE_PROJECT_NAME:-opensre}"

CONTAINERS=(
  opensre-postgres
  opensre-config-service
  opensre-neo4j
  opensre-litellm
  opensre-sre-agent
  opensre-web-ui
  opensre-slack-bot
  opensre-teams-bot
)

for name in "${CONTAINERS[@]}"; do
  if ! docker ps -a --format '{{.Names}}' | grep -qx "$name"; then
    continue
  fi

  proj="$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project"}}' "$name" 2>/dev/null || true)"
  if [[ -n "$proj" && "$proj" != "$PROJECT" ]]; then
    echo "compose-reconcile: removing $name (compose project $proj → $PROJECT)"
    docker rm -f "$name" >/dev/null
  fi
done
