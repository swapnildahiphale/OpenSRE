#!/usr/bin/env bash
# Create OpenSRE self-hosted K8s secrets from repo root .env (tracked in OpenSRE-private).
# Passwords in deploy/values.site.*.yaml should match DATABASE_URL / NEO4J_* overrides below.
# Usage: ./scripts/create-self-hosted-k8s-secrets.sh [namespace]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NS="${1:-opensre}"
ENV_FILE="${ROOT}/.env"
PG_PASSWORD="opensre-pilot-pg-password"
NEO4J_PASSWORD="opensre-pilot-neo4j-password"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE — copy .env.example and fill in values." >&2
  exit 1
fi

# shellcheck disable=SC1090
set -a
source "$ENV_FILE"
set +a

: "${ANTHROPIC_API_KEY:?ANTHROPIC_API_KEY required in .env}"

ADMIN_TOKEN="${ADMIN_TOKEN:-local-admin-token}"
TOKEN_PEPPER="${TOKEN_PEPPER:-localdev-pepper-must-be-32-chars-minimum!!}"
IMPERSONATION_JWT_SECRET="${IMPERSONATION_JWT_SECRET:-local-dev-impersonation-secret-32chars!!}"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# --- config-service ---
cat >"$TMP/config-service.env" <<EOF
DATABASE_URL=postgresql+psycopg2://opensre:${PG_PASSWORD}@opensre-postgresql.${NS}.svc.cluster.local:5432/opensre?sslmode=disable
ADMIN_TOKEN=${ADMIN_TOKEN}
TOKEN_PEPPER=${TOKEN_PEPPER}
IMPERSONATION_JWT_SECRET=${IMPERSONATION_JWT_SECRET}
ADMIN_AUTH_MODE=token
TEAM_AUTH_MODE=token
LOG_LEVEL=${LOG_LEVEL:-INFO}
LOG_FORMAT=json
EOF

# --- sre-agent: .env minus keys we override for in-cluster ---
grep -v '^#' "$ENV_FILE" | grep -v '^$' | grep -vE '^(NEO4J_URI|NEO4J_USERNAME|NEO4J_PASSWORD|NEO4J_DATABASE|CONFIG_SERVICE_URL|OPENSRE_TENANT_ID|OPENSRE_TEAM_ID|CLAUDE_CONFIG_DIR|AGENT_TIMEOUT_SECONDS|MEMORY_PRE_RECALL_ENABLED|MEMORY_PRE_TOPOLOGY_ENABLED|AWS_PROFILE|AWS_DEFAULT_REGION|AWS_REGION)=' \
  >"$TMP/sre-agent.env" || true
{
  echo "CONFIG_SERVICE_URL=http://opensre-config-service.${NS}.svc.cluster.local:8080"
  echo "OPENSRE_TENANT_ID=pilot"
  echo "OPENSRE_TEAM_ID=default"
  echo "NEO4J_URI=bolt://opensre.${NS}.svc.cluster.local:7687"
  echo "NEO4J_USERNAME=neo4j"
  echo "NEO4J_PASSWORD=${NEO4J_PASSWORD}"
  echo "NEO4J_DATABASE=${NEO4J_DATABASE:-neo4j}"
  echo "CLAUDE_CONFIG_DIR=/data/agent-sessions"
  echo "AGENT_TIMEOUT_SECONDS=${AGENT_TIMEOUT_SECONDS:-600}"
  echo "MEMORY_PRE_RECALL_ENABLED=${MEMORY_PRE_RECALL_ENABLED:-false}"
  echo "MEMORY_PRE_TOPOLOGY_ENABLED=${MEMORY_PRE_TOPOLOGY_ENABLED:-true}"
  echo "AWS_PROFILE=${AWS_PROFILE:-your-aws-profile}"
  echo "AWS_DEFAULT_REGION=${AWS_DEFAULT_REGION:-us-west-1}"
  echo "AWS_REGION=${AWS_REGION:-us-west-1}"
} >>"$TMP/sre-agent.env"

# --- web-ui: chart sets service URLs; secret can hold optional extras ---
cat >"$TMP/web-ui.env" <<EOF
# Optional overrides (chart templates set CONFIG_SERVICE_URL / AGENT_SERVICE_URL)
WEB_UI_COOKIE_SECURE=0
EOF

kubectl create namespace "$NS" --dry-run=client -o yaml | kubectl apply -f -
kubectl label namespace "$NS" app.kubernetes.io/managed-by=Helm --overwrite 2>/dev/null || true
kubectl annotate namespace "$NS" meta.helm.sh/release-name=opensre meta.helm.sh/release-namespace="$NS" --overwrite 2>/dev/null || true

kubectl -n "$NS" delete secret opensre-config-service-env opensre-sre-agent-env opensre-web-ui-env \
  --ignore-not-found

kubectl -n "$NS" create secret generic opensre-config-service-env \
  --from-env-file="$TMP/config-service.env"
kubectl -n "$NS" create secret generic opensre-sre-agent-env \
  --from-env-file="$TMP/sre-agent.env"
kubectl -n "$NS" create secret generic opensre-web-ui-env \
  --from-env-file="$TMP/web-ui.env"

echo "Secrets created in namespace ${NS}:"
kubectl -n "$NS" get secret opensre-config-service-env opensre-sre-agent-env opensre-web-ui-env
