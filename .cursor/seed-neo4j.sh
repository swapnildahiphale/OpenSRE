#!/usr/bin/env bash
# ============================================================================
# OpenSRE — one-time Neo4j knowledge-graph seed
# ============================================================================
# Loads the otel-demo service topology (scripts/populate_neo4j.cypher) into Neo4j
# so topology-aware investigations and blast-radius queries work out of the box.
#
# IMPORTANT: this only seeds when the graph is EMPTY. The seed cypher begins with
# `MATCH (n) DETACH DELETE n`, so running it against a populated graph would wipe
# real data. Guarding on emptiness makes this safe to call on every boot — a
# fresh environment gets seeded once, and later restarts leave existing data
# (topology edits, memory episodes) untouched.
#
# We load the cypher inside the neo4j container via cypher-shell because in the
# dev compose file the neo4j service sits on an internal-only network, so its
# bolt port is not published to the host.
# ============================================================================

set -euo pipefail

CONTAINER="opensre-neo4j"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
CYPHER_FILE="$REPO_ROOT/scripts/populate_neo4j.cypher"
ENV_FILE="$REPO_ROOT/.env"

# Read Neo4j credentials from the environment, falling back to the repo .env
# (the compose source of truth). We deliberately do not hardcode a default
# password here so no secret value lives in the committed script.
read_env() { grep -E "^$1=" "$ENV_FILE" 2>/dev/null | tail -1 | cut -d= -f2-; }
NEO4J_USER="${NEO4J_USERNAME:-$(read_env NEO4J_USERNAME)}"
NEO4J_PASS="${NEO4J_PASSWORD:-$(read_env NEO4J_PASSWORD)}"
NEO4J_USER="${NEO4J_USER:-neo4j}"

if [ ! -f "$CYPHER_FILE" ]; then
  echo "[seed-neo4j] $CYPHER_FILE not found — skipping."
  exit 0
fi

# Helper: run a cypher query and return the raw plain output.
run_cypher() {
  docker exec -i "$CONTAINER" cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASS" \
    --format plain "$1" 2>/dev/null
}

# Wait until Neo4j accepts bolt queries (up to ~60s). Fresh boots need this
# because make dev returns before Neo4j has finished starting.
echo "[seed-neo4j] Waiting for Neo4j to accept queries..."
for i in $(seq 1 60); do
  if run_cypher "RETURN 1;" >/dev/null 2>&1; then
    break
  fi
  if [ "$i" -eq 60 ]; then
    echo "[seed-neo4j] Neo4j not ready after 60s — skipping seed (non-fatal)."
    exit 0
  fi
  sleep 1
done

# Only seed when the graph is empty, so we never clobber existing data.
NODE_COUNT="$(run_cypher "MATCH (n) RETURN count(n) AS c;" | sed -n '2p' | tr -d '[:space:]')"
NODE_COUNT="${NODE_COUNT:-0}"

if [ "$NODE_COUNT" != "0" ]; then
  echo "[seed-neo4j] Graph already has $NODE_COUNT nodes — leaving it untouched."
  exit 0
fi

echo "[seed-neo4j] Empty graph — loading otel-demo topology from populate_neo4j.cypher"
docker exec -i "$CONTAINER" cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASS" \
  --format plain < "$CYPHER_FILE" >/dev/null 2>&1 || true

SEEDED="$(run_cypher "MATCH (n) RETURN count(n) AS c;" | sed -n '2p' | tr -d '[:space:]')"
echo "[seed-neo4j] Done. Graph now has ${SEEDED:-?} nodes."
