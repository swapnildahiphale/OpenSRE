"""Add team_tokens.display_name for SSO persona.

Revision ID: 20260909_token_disp_name
Revises: 20260901_sso_configs_oidc
Create Date: 2026-09-09

alembic_version.version_num is varchar(32); keep the revision id short.
"""

import sqlalchemy as sa
from alembic import op

revision = "20260909_token_disp_name"
down_revision = "20260901_sso_configs_oidc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "team_tokens",
        sa.Column("display_name", sa.String(length=256), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("team_tokens", "display_name")
