"""Add parent_agent_id column to agent_tool_calls.

Completes the stable-invocation-identity fix: agent_id/parent_agent_id now carry the
tool_use_id of the dispatching Task/Agent call (never reused), not the SDK's own
agent_id (which the SDK reuses across unrelated dispatches within a run). Additive
only; no backfill of historical rows.

Revision ID: 20260702_tool_call_parent_id
Revises: 20260701_agent_tool_call_depth
Create Date: 2026-07-02

Note: revision id is intentionally shorter than the natural
"20260702_agent_tool_call_parent_id" name — alembic_version.version_num is
varchar(32) and that longer id (34 chars) overflows it (confirmed by a failed
upgrade against a live dev DB: StringDataRightTruncation on the bookkeeping
UPDATE, though the add_column DDL itself succeeded and rolled back cleanly).
"""

import sqlalchemy as sa
from alembic import op

revision = "20260702_tool_call_parent_id"
down_revision = "20260701_agent_tool_call_depth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agent_tool_calls",
        sa.Column("parent_agent_id", sa.String(64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("agent_tool_calls", "parent_agent_id")
