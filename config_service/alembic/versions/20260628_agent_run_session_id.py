"""Add sdk_session_id column to agent_runs table.

Stores the Claude Agent SDK session id so a conversation can be resumed
(ClaudeAgentOptions.resume) after the agent process recycles.

Revision ID: 20260628_agent_run_session_id
Revises: 20260312_agent_run_thoughts
Create Date: 2026-06-28
"""

import sqlalchemy as sa
from alembic import op

revision = "20260628_agent_run_session_id"
down_revision = "20260312_agent_run_thoughts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agent_runs",
        sa.Column("sdk_session_id", sa.String(length=128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("agent_runs", "sdk_session_id")
