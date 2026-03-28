# `database/` — OpenSRE Database + Infra Tooling *(implemented)*

This directory contains the infrastructure and operational scripts for OpenSRE’s database layer (currently **AWS RDS PostgreSQL**) and internal-only access patterns.

## Important: shared OLTP direction

Today, the DB is most heavily exercised by `config_service/`, but the intent is for this Postgres cluster to become the **shared OLTP** for OpenSRE:
- config + audit logs (already)
- orchestrator provisioning state (now starting)
- agent runs / traces / tool calls
- pipeline run tracking + eval artifacts metadata
- knowledge base metadata (indices, retrieval logs, lineage)

This means we will continue adding tables/schemas over time, with clear ownership boundaries per subsystem.

## Migrations strategy (current intent)

We are intentionally **not** centralizing migrations into a single monolithic migration set yet (it creates coupling and slows iteration).

Instead:
- each service owns its tables and migrations (e.g., `config_service/alembic/`)
- services share the same Postgres cluster, but should use clear naming (and later Postgres schemas like `config`, `pipeline`, `orchestrator`, `agent`, `kb`)
- we can later add a `database/` “migration runner” that executes each subsystem’s migrations in a controlled order for dev/prod.

## What’s in here

- **Terraform**: `infra/terraform/`
  - RDS PostgreSQL in **private subnets**
  - Secrets Manager secret for DB credentials
  - internal-only app endpoint pattern via ECS/ALB stacks (used by `config_service/`)
  - jumpbox stack for SSM port-forwarding (no VPN required)
- **Scripts**: `scripts/`
  - pull RDS secret into `config_service/.env`
  - SSM tunnels to RDS and internal ALB
  - `psql` helpers via tunnel

## Key design points

- **Private-by-default**: DB and internal ALB are not internet-facing.
- **Access via SSM**: local access is typically through SSM port-forwarding.
- **Secrets in Secrets Manager**: credentials are managed via AWS Secrets Manager and pulled into local env files only for development.

## Common commands

From `database/`:

- Pull RDS secret into `config_service/.env`:
  - `AWS_PROFILE=playground AWS_REGION=us-west-2 ./scripts/pull_rds_secret_to_env.sh`
- Start an SSM tunnel to RDS:
  - `AWS_PROFILE=playground AWS_REGION=us-west-2 ./scripts/rds_tunnel.sh`
- Connect via `psql` (requires tunnel):
  - `./scripts/psql_via_tunnel.sh`
- Tunnel to internal ALB (UI):
  - `AWS_PROFILE=playground AWS_REGION=us-west-2 ./scripts/ui_tunnel_aws.sh`

## Terraform docs

- `infra/terraform/README.md` (RDS module notes and cautions)
- `infra/terraform/app/README.md` (internal app endpoint deployment)
- `infra/terraform/jumpbox/README.md` (SSM access pattern)


