"""Add agent_id and depth columns to agent_tool_calls.

Nested-agent attribution (hook-based): agent_id is the SDK agent_id of the
agent that ran the call (None for root), and depth is the nesting depth
(0 == root). Backs the recursive agent-tree rendering in the web UI. Both
columns are additive; no backfill of historical rows (only runs recorded after
this ships get correct attribution).

Revision ID: 20260701_agent_tool_call_depth
Revises: 20260628_pending_changes_schema
Create Date: 2026-07-01
"""

import sqlalchemy as sa
from alembic import op

revision = "20260701_agent_tool_call_depth"
down_revision = "20260628_pending_changes_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agent_tool_calls", sa.Column("agent_id", sa.String(64), nullable=True)
    )
    op.add_column(
        "agent_tool_calls",
        sa.Column("depth", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("agent_tool_calls", "depth")
    op.drop_column("agent_tool_calls", "agent_id")
