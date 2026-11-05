"""Add investigation_followups table for channel nudge delivery.

Resolution state lives on the Neo4j Episode. This table holds only
nudge timing, asker identity, and Teams ConversationReference.

Revision ID: 20260916_inv_followups
Revises: 20260909_token_disp_name
Create Date: 2026-09-16
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "20260916_inv_followups"
down_revision = "20260909_token_disp_name"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "investigation_followups",
        sa.Column("correlation_id", sa.String(255), primary_key=True),
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column("team_node_id", sa.String(128), nullable=False),
        sa.Column("entry_channel", sa.String(16), nullable=False),
        sa.Column("trigger_actor_name", sa.String(128), nullable=True),
        sa.Column("trigger_actor_teams_id", sa.String(128), nullable=True),
        sa.Column("conversation_ref", JSONB, nullable=True),
        sa.Column("nudge_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("nudge_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_nudge_text", sa.String(1024), nullable=True),
        sa.Column("stopped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_investigation_followups_due",
        "investigation_followups",
        ["nudge_due_at"],
        postgresql_where=sa.text("stopped_at IS NULL"),
    )
    op.create_index(
        "ix_investigation_followups_team",
        "investigation_followups",
        ["org_id", "team_node_id"],
    )


def downgrade():
    op.drop_index(
        "ix_investigation_followups_team", table_name="investigation_followups"
    )
    op.drop_index("ix_investigation_followups_due", table_name="investigation_followups")
    op.drop_table("investigation_followups")
