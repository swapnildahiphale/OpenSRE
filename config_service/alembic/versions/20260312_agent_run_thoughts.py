"""Add thoughts JSONB column to agent_runs table.

Stores agent reasoning/thinking events captured during investigation,
enabling the TraceViewer to display collapsible reasoning blocks
interleaved with tool calls.

Revision ID: 20260312_agent_run_thoughts
Revises: 20260311_investigation_episodes
Create Date: 2026-03-12
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "20260312_agent_run_thoughts"
down_revision = "20260311_investigation_episodes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agent_runs",
        sa.Column("thoughts", JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("agent_runs", "thoughts")
