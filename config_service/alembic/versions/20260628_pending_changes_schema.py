"""Reconcile pending_config_changes table with the PendingConfigChange model.

The table was created by 20260113_consolidated.py with an older schema
(change_id PK, requested_config, change_diff, justification) that never matched
the current SQLAlchemy model / writer (id PK, change_type, change_path,
proposed_value, previous_value, reason). As a result every query/insert raised
UndefinedColumn and the entire pending-changes / approval subsystem (Proposed
Changes list, approve, reject, AI-proposed changes) was non-functional.

The table has no rows in any deployed environment (the feature could never run),
so this migration simply drops and recreates it to match the model exactly.

Revision ID: 20260628_pending_changes_schema
Revises: 20260312_agent_run_thoughts
Create Date: 2026-06-28
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "20260628_pending_changes_schema"
# Chained after 20260628_agent_run_session_id. Both migrations were authored the
# same day on separate branches and originally shared down_revision
# 20260312_agent_run_thoughts; merging the branches left the Alembic DAG with two
# heads. Linearize here so `alembic upgrade head` resolves to a single head.
down_revision = "20260628_agent_run_session_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 0 rows in practice (the feature never ran) -> safe to drop & recreate.
    op.drop_table("pending_config_changes")

    op.create_table(
        "pending_config_changes",
        sa.Column("id", sa.String(64), nullable=False),
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column("node_id", sa.String(128), nullable=False),
        sa.Column("change_type", sa.String(32), nullable=False),
        sa.Column("change_path", sa.String(256), nullable=True),
        sa.Column("proposed_value", JSONB, nullable=True),
        sa.Column("previous_value", JSONB, nullable=True),
        sa.Column("requested_by", sa.String(128), nullable=False),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("reviewed_by", sa.String(128), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_comment", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["org_id", "node_id"],
            ["org_nodes.org_id", "org_nodes.node_id"],
            name="fk_pending_config_changes_node",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_pending_config_changes_org_id", "pending_config_changes", ["org_id"]
    )
    op.create_index(
        "ix_pending_config_changes_status", "pending_config_changes", ["status"]
    )
    op.create_index(
        "ix_pending_config_changes_requested_at",
        "pending_config_changes",
        ["requested_at"],
    )


def downgrade() -> None:
    # Restore the original (pre-reconciliation) consolidated schema.
    op.drop_table("pending_config_changes")
    op.create_table(
        "pending_config_changes",
        sa.Column("change_id", sa.String(64), nullable=False),
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column("node_id", sa.String(128), nullable=False),
        sa.Column("requested_config", JSONB, nullable=False),
        sa.Column("change_diff", JSONB, nullable=True),
        sa.Column("requested_by", sa.String(128), nullable=False),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("justification", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("reviewed_by", sa.String(128), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_comment", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("change_id"),
    )
    op.create_index(
        "ix_pending_config_changes_org_node",
        "pending_config_changes",
        ["org_id", "node_id"],
    )
    op.create_index(
        "ix_pending_config_changes_status", "pending_config_changes", ["status"]
    )
