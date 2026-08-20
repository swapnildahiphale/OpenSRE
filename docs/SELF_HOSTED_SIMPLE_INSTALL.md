# Self-Hosted OpenSRE — Simple Mode on Kubernetes

Deploy OpenSRE in **simple mode** (`server_simple.py`) using the umbrella Helm chart and `values.self-hosted-simple.yaml`.

## Prerequisites

- `kubectl`, Helm 3
- Cluster with a default StorageClass (EBS CSI on EKS)
- Optional: Ingress controller (nginx, Apisix, or ALB)
- Container registry with pull access for your chosen image references (public Docker Hub defaults work out of the box)

Simple-mode image defaults (tag **v1.2.0**):

- `swapnildahiphale/opensre-sre-agent:v1.2.0`
- `swapnildahiphale/opensre-config-service:v1.2.0`
- `swapnildahiphale/opensre-web-ui:v1.2.0`
- `swapnildahiphale/opensre-teams-bot:v1.2.0` (chart service off unless you enable `teamsBot`)

Override only in a local `my-site.yaml` if you use a private registry.

## Quick install (generic)

```bash
helm dependency update charts/opensre

kubectl create namespace opensre

# Create secrets — see "Required secrets" table below for keys.
kubectl create secret generic opensre-config-service-env -n opensre \
  --from-literal=DATABASE_URL='postgresql://opensre:YOUR_PASSWORD@opensre-postgresql:5432/opensre' \
  --from-literal=ADMIN_TOKEN='change-me' \
  --from-literal=TOKEN_PEPPER='change-me' \
  --from-literal=IMPERSONATION_JWT_SECRET='change-me' \
  --from-literal=ADMIN_AUTH_MODE=token \
  --from-literal=TEAM_AUTH_MODE=token
kubectl create secret generic opensre-sre-agent-env -n opensre \
  --from-literal=ANTHROPIC_API_KEY='sk-ant-...' \
  --from-literal=CONFIG_SERVICE_URL='http://opensre-config-service:8080' \
  --from-literal=NEO4J_URI='bolt://opensre-neo4j:7687' \
  --from-literal=NEO4J_USER='neo4j' \
  --from-literal=NEO4J_PASSWORD='change-me'
# opensre-web-ui-env is optional; the chart sets in-cluster service URLs by default.

helm upgrade --install opensre charts/opensre \
  -n opensre --create-namespace \
  -f charts/opensre/values.self-hosted-simple.yaml
```

## Required secrets

| Secret | Keys (representative) |
|--------|------------------------|
| `opensre-config-service-env` | `DATABASE_URL`, `ADMIN_TOKEN`, `TOKEN_PEPPER`, `IMPERSONATION_JWT_SECRET`, `ADMIN_AUTH_MODE=token`, `TEAM_AUTH_MODE=token` |
| `opensre-sre-agent-env` | `ANTHROPIC_API_KEY`, `CONFIG_SERVICE_URL`, `NEO4J_*`, `CLAUDE_CONFIG_DIR`, integration vars from `.env` |
| `opensre-web-ui-env` | Optional; chart sets in-cluster service URLs |

Embedded Postgres password: set `postgresql.auth.password` in site overlay and use the same value in `DATABASE_URL`.

Embedded Neo4j: set `neo4j.neo4j.password` in site overlay; agent `NEO4J_URI=bolt://<neo4j-svc>.<ns>.svc.cluster.local:7687`.

## Database migrations (embedded Postgres)

`values.self-hosted-simple.yaml` sets `services.configService.migrations.hookEnabled: false` because Helm **hook Jobs** run before the Bitnami Postgres subchart is ready. Migrations instead run as an **initContainer** on config-service (`migrations.enabled: true`, the default).

For external RDS, use chart defaults (`hookEnabled: true`) — see the Migrations section in `charts/opensre/README.md`.

## Seed org / team (first install)

```bash
kubectl -n opensre exec deploy/opensre-config-service -- \
  env SEED_ORG_ID=pilot SEED_TEAM_NODE_ID=default SEED_TEAM_NAME=Pilot \
  python scripts/seed_demo_data.py
```

Issue a team token (admin API):

```bash
curl -s -X POST "http://localhost:8080/api/v1/admin/orgs/pilot/teams/default/tokens" \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d '{"label":"pilot"}'
```

(Port-forward config-service first if needed.)

## RBAC smoke test

```bash
kubectl auth can-i list pods \
  --as=system:serviceaccount:opensre:opensre-agent \
  -n otel-demo
```

## Port-forward (no DNS)

```bash
kubectl port-forward -n opensre svc/opensre-web-ui 3002:3000
# http://localhost:3002 — log in with team token via /api/session/login
```

## Site overlay

Copy the example overlay and fill in your registry, host, and namespace:

```bash
cp charts/opensre/values.examples/site-overlay.yaml.example my-site.yaml
# edit my-site.yaml — do not commit secrets to a public fork
```

```bash
helm upgrade --install opensre charts/opensre \
  -n opensre --create-namespace \
  -f charts/opensre/values.self-hosted-simple.yaml \
  -f my-site.yaml
```

Company-specific overlays (hosts, IRSA, extra skills images) belong in a private overlay repo, not in this tree.

## Neo4j backups (optional)

Community Neo4j has no online backup. The chart can run a nightly offline dump to S3 (`neo4j.backup.enabled`). The database is scaled to 0 for a few minutes. See `charts/opensre/values.examples/site-overlay.yaml.example` for the knobs. Restore is `neo4j-admin database load` against the data PVC using the same image; keep that procedure in the site runbook, not in public examples with real bucket names.
