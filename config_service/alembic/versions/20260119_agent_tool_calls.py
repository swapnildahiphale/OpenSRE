"""Add agent_tool_calls table for detailed tool execution traces.

Revision ID: 20260119_tool_calls
Revises: 20260118_service_dependencies
Create Date: 2026-01-19
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260119_tool_calls"
down_revision = "20260118_service_dependencies"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_tool_calls",
        sa.Column("id", sa.String(64), nullable=False),
        sa.Column("run_id", sa.String(64), nullable=False),
        sa.Column("tool_name", sa.String(128), nullable=False),
        sa.Column(
            "tool_input",
            sa.JSON().with_variant(postgresql.JSONB, "postgresql"),
            nullable=True,
        ),
        sa.Column("tool_output", sa.Text(), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="success"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("sequence_number", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_agent_tool_calls_run_id", "agent_tool_calls", ["run_id"], unique=False
    )
    op.create_index(
        "ix_agent_tool_calls_tool_name", "agent_tool_calls", ["tool_name"], unique=False
    )
    op.create_index(
        "ix_agent_tool_calls_started_at",
        "agent_tool_calls",
        ["started_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_agent_tool_calls_started_at", table_name="agent_tool_calls")
    op.drop_index("ix_agent_tool_calls_tool_name", table_name="agent_tool_calls")
    op.drop_index("ix_agent_tool_calls_run_id", table_name="agent_tool_calls")
    op.drop_table("agent_tool_calls")
