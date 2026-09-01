"""Reconcile sso_configs with the SSOConfig OIDC model.

The table was created by 20260113_consolidated.py with an older schema
(provider, saml_*, oidc_client_id, oidc_client_secret, oidc_discovery_url)
that never matched the current SQLAlchemy model (provider_type, issuer,
client_id, tenant_id, claim mappings). Admin → SSO
and seed_demo_data both query provider_type and fail with UndefinedColumn.

The table has no usable rows (the Admin form could never persist against the
old columns), so this migration drops and recreates it to match the model.

Revision ID: 20260901_sso_configs_oidc
Revises: 20260818_widen_corr_id
Create Date: 2026-09-01
"""

import sqlalchemy as sa
from alembic import op

# alembic_version.version_num is varchar(32); keep this id short.
revision = "20260901_sso_configs_oidc"
down_revision = "20260818_widen_corr_id"
branch_labels = None
depends_on = None


def _create_sso_configs() -> None:
    op.create_table(
        "sso_configs",
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "provider_type",
            sa.String(32),
            nullable=False,
            server_default="oidc",
        ),
        sa.Column("provider_name", sa.String(128), nullable=True),
        sa.Column("issuer", sa.String(512), nullable=True),
        sa.Column("client_id", sa.String(256), nullable=True),
        sa.Column(
            "scopes",
            sa.String(512),
            nullable=True,
            server_default="openid email profile",
        ),
        sa.Column("tenant_id", sa.String(128), nullable=True),
        sa.Column(
            "email_claim",
            sa.String(64),
            nullable=True,
            server_default="email",
        ),
        sa.Column(
            "name_claim",
            sa.String(64),
            nullable=True,
            server_default="name",
        ),
        sa.Column(
            "groups_claim",
            sa.String(64),
            nullable=True,
            server_default="groups",
        ),
        sa.Column("admin_group", sa.String(256), nullable=True),
        sa.Column("allowed_domains", sa.String(1024), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("updated_by", sa.String(128), nullable=True),
        sa.PrimaryKeyConstraint("org_id"),
    )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()
    if "sso_configs" not in tables:
        _create_sso_configs()
        return

    columns = {col["name"] for col in inspector.get_columns("sso_configs")}
    # Skip if a later environment already matches the model (create_all / manual).
    if "provider_type" in columns and "client_secret_encrypted" not in columns:
        return

    op.drop_table("sso_configs")
    _create_sso_configs()


def downgrade() -> None:
    op.drop_table("sso_configs")
    op.create_table(
        "sso_configs",
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("saml_metadata_url", sa.Text(), nullable=True),
        sa.Column("saml_entity_id", sa.String(256), nullable=True),
        sa.Column("oidc_client_id", sa.String(256), nullable=True),
        sa.Column("oidc_client_secret", sa.Text(), nullable=True),
        sa.Column("oidc_discovery_url", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("org_id"),
    )
