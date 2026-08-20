# `charts/opensre/` — OpenSRE on Kubernetes (EKS)

This is the **umbrella Helm chart** for deploying OpenSRE services into an AWS EKS cluster.

## Assumptions (AWS + EKS)

- Ingress: **AWS Load Balancer Controller (ALB)**
- Secrets: **External Secrets Operator (ESO)** syncing from **AWS Secrets Manager**
- Database: external **Postgres** (typically RDS). Apps read `DATABASE_URL` from a Kubernetes Secret.

## Secrets contract (required)

This chart expects these Kubernetes Secrets (typically created by ESO):

- **Database URL**
  - Secret: `opensre-database-url`
  - Key: `DATABASE_URL`
- **Config service**
  - Secret: `opensre-config-service`
  - Keys: `ADMIN_TOKEN`, `TOKEN_PEPPER`, `IMPERSONATION_JWT_SECRET`
- **Agent**
  - Secret: `opensre-openai`
  - Key: `api_key`

Optional (single-tenant/dev):
- **Agent team token**
  - Set `services.agent.staticTeamToken.enabled=true` and point it at a K8s Secret containing `OPENSRE_TEAM_TOKEN`.

Configure the AWS Secrets Manager keys under `externalSecrets.contract.*` in `values.yaml`.

## Web UI / Agent runs

For enterprise safety, the recommended flow is:
- `web_ui` calls `orchestrator` (admin-authenticated)
- `orchestrator` mints a **short-lived team impersonation token** server-side (JWT)
- `orchestrator` calls the `agent` with `X-OpenSRE-Team-Token`

This avoids exposing team tokens to browsers.

## Admin auth (OIDC-first) + RBAC

OpenSRE supports **OIDC JWTs** for admin auth (recommended for enterprise). The `config_service` is the source of truth for admin permissions via `GET /api/v1/auth/me`.

### Configure OIDC for config_service

Set these in `values.yaml`:

- `services.configService.adminAuthMode`: `oidc` or `both`
- `services.configService.oidc.enabled`: `true`
- `services.configService.oidc.issuer`, `audience`, `jwksUrl` (or `jwksJson` for dev)
- `services.configService.oidc.adminGroup`: the group that qualifies as an admin

### Configure admin RBAC (group → permissions)

`config_service` returns a `permissions[]` list for admins. Orchestrator enforces **endpoint-scoped permissions** (and can optionally require `admin:*`).

- **Defaults**:
  - `services.configService.adminPermissionsDefault: "admin:*"` (backwards-compatible superuser)
  - `services.configService.adminGroupPermissionsJson: "{}"`

Example:

```yaml
services:
  configService:
    adminAuthMode: oidc
    oidc:
      enabled: true
      issuer: "https://your-issuer/"
      audience: "opensre"
      jwksUrl: "https://your-issuer/.well-known/jwks.json"
      adminGroup: "opensre-admins"
    adminPermissionsDefault: "admin:read"
    adminGroupPermissionsJson: >
      {"opensre-admins":["admin:*"],
       "opensre-provisioners":["admin:provision","admin:provision:read"],
       "opensre-operators":["admin:agent:run"]}

  orchestrator:
    requireAdminStar: false
    requiredPermissions:
      provisionTeam: admin:provision
      provisionRead: admin:provision:read
      agentRun: admin:agent:run
```

### Web UI OIDC login

The `web_ui` supports an **OIDC Authorization Code + PKCE** login flow.

Configure these values:
- `services.webUi.cookieSecure: true` (when served over HTTPS)
- `services.webUi.oidc.enabled: true`
- `services.webUi.oidc.publicBaseUrl`: external https URL for the UI (used to compute callback URL)
- `services.webUi.oidc.authorizationEndpoint`, `tokenEndpoint`, `clientId`
- `services.webUi.oidc.clientSecret.secretName/secretKey`: points to a K8s Secret (recommended via ESO)

### Impersonation JWT hardening knobs

`config_service` mints short-lived impersonation JWTs and (by default) validates them by signature + expiry.

- **Audience**: the chart sets `IMPERSONATION_JWT_AUDIENCE=opensre-agent-runtime` to scope these tokens to the agent runtime.
- **Optional DB allowlist**: you can enable DB-backed JTI tracking / allowlist by setting:
  - `IMPERSONATION_JTI_DB_LOGGING=1` (record `jti` rows at mint-time)
  - `IMPERSONATION_JTI_DB_REQUIRE=1` (require that `jti` exists during verification)

## Migrations

Config-service schema migrations can run in two ways (controlled by `services.configService.migrations`):

| Knob | Default | What it does |
|------|---------|----------------|
| `hookEnabled` | `true` | Pre-install/pre-upgrade **Helm hook Job** (`opensre-config-service-migrate` in `templates/migrations.yaml`) |
| `enabled` | `true` | **initContainer** on the config-service Deployment (`alembic upgrade head` before the app starts) |

**External database (RDS, etc.):** keep defaults — the hook Job runs before deploy; the initContainer is redundant but harmless (idempotent).

**Embedded Postgres** (`postgresql.enabled: true`, e.g. `values.self-hosted-simple.yaml`): set `hookEnabled: false`. Hook Jobs run before subchart pods exist, so migrations would fail; the initContainer runs when config-service starts, after Postgres is up.

Other migration hook Jobs (when those services are enabled):

- `opensre-orchestrator-migrate`: `python -m opensre_orchestrator.db_migrate`
- `opensre-ai-pipeline-migrate`: `python scripts/db_migrate.py`

All migration steps are **idempotent** and safe to re-run.

## Install

```bash
helm upgrade --install opensre charts/opensre \
  -n opensre --create-namespace \
  -f charts/opensre/values.self-hosted-simple.yaml
```

### Self-hosted profile (recommended)

See `charts/opensre/values.self-hosted-simple.yaml` for the supported public self-hosted profile (simple mode with embedded Postgres/Neo4j; Docker Hub image pins for v1.2.0). Full walkthrough: `docs/SELF_HOSTED_SIMPLE_INSTALL.md`.

### Site overlay (hosts, TLS, private registry)

Copy `charts/opensre/values.examples/site-overlay.yaml.example` and merge with the self-hosted profile:

```bash
cp charts/opensre/values.examples/site-overlay.yaml.example my-site.yaml
# edit my-site.yaml — do not commit secrets to a public fork

helm upgrade --install opensre charts/opensre \
  -n opensre --create-namespace \
  -f charts/opensre/values.self-hosted-simple.yaml \
  -f my-site.yaml
```

## Production hardening knobs

This chart supports:
- **resources**: per-service CPU/memory requests+limits under `services.<svc>.resources`
- **livenessProbe**: per-service liveness probes under `services.<svc>.livenessProbe`
- **PDB**: per-service PodDisruptionBudget under `services.<svc>.pdb`
- **HPA**: per-service HorizontalPodAutoscaler under `services.<svc>.hpa`


