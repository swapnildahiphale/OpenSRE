# OpenSRE Config Service

Hierarchical configuration management for OpenSRE agents and teams.

## What this service does

- **Stores config** at any node in an org tree (org → team → sub-team), in **PostgreSQL (AWS RDS)**.
- **Resolves effective team config** by **N-level inheritance** (root → … → team), using deep-merge rules.
- Provides:
  - **Team API + UI** (view effective config, edit team overrides)
  - **Admin API + UI** (manage org tree, patch node configs, audit, rollback, tokens)

## Key behaviors

- **Merge semantics**: dicts merge recursively, lists replace entirely, scalars replace.
- **Writes are PATCH-like**:
  - `PUT /api/v1/config/me` deep-merges payload into existing team overrides.
  - `PUT /api/v1/admin/.../config` deep-merges payload into node config.
- **Immutables**: some fields (e.g. `team_name`) are server-enforced immutable.
- **Audit**: every node/team config write creates an audit row with diff + full snapshot.

## Quickstart (local dev against AWS RDS)

### Prereqs

- Python 3.9+
- AWS CLI authenticated (`AWS_PROFILE=playground`, `AWS_REGION=us-west-2`)
- Terraform installed (for tunnels/deploy)

Optional:
- If you prefer, use the provided `Makefile` (run `make help`).

### 1) Install deps

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2) Pull DB secret to `.env`

```bash
../database/scripts/pull_rds_secret_to_env.sh
```

### 3) Start the RDS tunnel (SSM)

```bash
../database/scripts/rds_tunnel.sh
```

### 4) Migrate + seed demo data

```bash
./scripts/db_migrate.sh
python3 scripts/seed_demo_data.py
```

### 5) Run the server

```bash
set -a
source .env
set +a
uvicorn src.api.main:app --reload --port 8080
```

Open:
- Team UI: `http://localhost:8080/`
- Admin UI: `http://localhost:8080/admin`

### 6) Issue a team token (demo) + call API

```bash
python3 scripts/issue_team_token.py --org-id org1 --team-node-id teamA
curl -H "Authorization: Bearer <TOKEN>" http://localhost:8080/api/v1/config/me/effective
```

## Deploy to AWS (internal-only)

This stack is **private** (no public endpoint):
- ECS Fargate in private subnets
- Internal ALB
- Access via SSM port-forward

### 1) Configure terraform vars (local file)

```bash
cp ../database/infra/terraform/app/terraform.tfvars.example ../database/infra/terraform/app/terraform.tfvars
```

### 2) Deploy

```bash
./scripts/deploy_app_ecs.sh
```

### 3) Tunnel to the internal ALB (UI)

```bash
LOCAL_PORT=8081 ./scripts/ui_tunnel_aws.sh
```

Open:
- `http://localhost:8081/`
- `http://localhost:8081/admin`

## API overview

### Team API

- `GET /api/v1/config/me/effective` - Get resolved team config with inheritance
- `GET /api/v1/config/me/raw` - Get raw team overrides only
- `PUT /api/v1/config/me` - Update team config (PATCH semantics; immutable fields rejected)
- `GET /api/v1/config/me/org-settings` - Get organization telemetry settings
- `PUT /api/v1/config/me/org-settings` - Update organization telemetry settings (admin-level preference)

### Admin API

- Org graph:
  - `GET /api/v1/admin/orgs/{org_id}/nodes`
  - `POST /api/v1/admin/orgs/{org_id}/nodes`
  - `PATCH /api/v1/admin/orgs/{org_id}/nodes/{node_id}`
- Node config:
  - `GET /api/v1/admin/orgs/{org_id}/nodes/{node_id}/config`
  - `PUT /api/v1/admin/orgs/{org_id}/nodes/{node_id}/config`
  - `POST /api/v1/admin/orgs/{org_id}/nodes/{node_id}/config/rollback`
  - `GET /api/v1/admin/orgs/{org_id}/nodes/{node_id}/audit`
- Org-wide audit:
  - `GET /api/v1/admin/orgs/{org_id}/audit`
  - `GET /api/v1/admin/orgs/{org_id}/audit/export?format=csv|json`
- Team tokens:
  - `POST /api/v1/admin/orgs/{org_id}/teams/{team_node_id}/tokens`
  - `POST /api/v1/admin/orgs/{org_id}/teams/{team_node_id}/tokens/{token_id}/revoke`
  - `GET /api/v1/admin/orgs/{org_id}/teams/{team_node_id}/tokens`

## Organization Settings (Telemetry)

**New in 2026-01-11:** Organizations can now control telemetry preferences at the org level.

### Database Schema

```sql
CREATE TABLE org_settings (
    org_id VARCHAR(64) PRIMARY KEY,
    telemetry_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_by VARCHAR(128)
);
```

### API Endpoints

#### GET `/api/v1/config/me/org-settings`

Get current organization settings (telemetry preference).

**Authentication:** Team token

**Response:**
```json
{
  "org_id": "extend",
  "telemetry_enabled": true,
  "updated_at": "2026-01-11T19:05:21.133463Z",
  "updated_by": "team_abc123"
}
```

**Note:** If no settings exist for the org, returns default: `telemetry_enabled: true`

#### PUT `/api/v1/config/me/org-settings`

Update organization settings (currently only telemetry preference).

**Authentication:** Team token (any team in the org can update org-level settings)

**Request:**
```json
{
  "telemetry_enabled": false
}
```

**Response:**
```json
{
  "org_id": "extend",
  "telemetry_enabled": false,
  "updated_at": "2026-01-11T19:10:30.456789Z",
  "updated_by": "team_abc123"
}
```

**Implementation Notes:**
- Creates or updates the `org_settings` record
- Records which team made the change in `updated_by` field
- Changes take effect immediately for telemetry collection (within 5 minutes)
- See `../docs/TELEMETRY_SYSTEM.md` for complete telemetry documentation

## Configuration / env

See `config/env.example`.

Notable vars:
- `TOKEN_PEPPER`: required (hashing for opaque team tokens)
- `ADMIN_TOKEN`: required if admin auth mode uses token
- `CONFIG_CACHE_BACKEND`: `memory` (default), `redis`, or `none`
- `REDIS_URL`: required if `CONFIG_CACHE_BACKEND=redis`

### OIDC (recommended for enterprise)

Enable OIDC for admin and/or team auth:
- `OIDC_ENABLED=1`
- `OIDC_ISSUER`, `OIDC_AUDIENCE`
- `OIDC_JWKS_URL` (recommended) or `OIDC_JWKS_JSON` (dev)
- `OIDC_GROUPS_CLAIM` (default: `groups`)
- `OIDC_ADMIN_GROUP` (default: `opensre-config-admin`)

Admin auth modes:
- `ADMIN_AUTH_MODE=token|oidc|both`

Team auth modes:
- `TEAM_AUTH_MODE=token|oidc|both`

### Admin RBAC (OIDC group → permissions)

`GET /api/v1/auth/me` returns `permissions[]` for admins.

Env:
- `ADMIN_PERMISSIONS_DEFAULT` (default: `admin:*`)
- `ADMIN_GROUP_PERMISSIONS_JSON` (JSON dict mapping group → permissions list)

Example:

```bash
export ADMIN_PERMISSIONS_DEFAULT="admin:read"
export ADMIN_GROUP_PERMISSIONS_JSON='{"opensre-admins":["admin:*"],"opensre-ops":["admin:agent:run"]}'
```

## Observability

- Health: `GET /health`
- Metrics: `GET /metrics`
  - includes `config_service_config_cache_events_total` for cache hit/miss/set

## Troubleshooting

- **RDS connection timeout**: ensure `./scripts/rds_tunnel.sh` is running (DB is private)
- **RDS SSL error**: tunnel DSN must use `sslmode=require`
- **Admin UI “Invalid admin token”**: ensure you’re using the correct base URL (AWS tunnel vs local)
- **ECS unhealthy**: confirm target group health check is `/health` and secrets/env are present

## Docs

- `docs/TECH_SPEC.md`: detailed design and schema notes
- `docs/USING_CONFIG_SERVICE.md`: how other services should call `/api/v1/config/me/*` (mock data + Python example)
