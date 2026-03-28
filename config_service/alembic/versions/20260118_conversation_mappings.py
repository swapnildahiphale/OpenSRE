"""Add conversation_mappings table for OpenAI conversation ID storage

Revision ID: 20260118_conversation_mappings
Revises: 20260114_canonical_format
Create Date: 2026-01-18

This migration adds a table to store mappings between our session identifiers
(like Slack thread IDs, GitHub PR IDs) and OpenAI conversation IDs.
This enables conversation resumption across multiple agent runs.
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260118_conversation_mappings"
down_revision = "20260114_canonical_format"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "conversation_mappings",
        sa.Column("session_id", sa.String(256), primary_key=True),
        sa.Column("openai_conversation_id", sa.String(128), nullable=False),
        sa.Column("org_id", sa.String(64), nullable=True),
        sa.Column("team_node_id", sa.String(128), nullable=True),
        sa.Column("session_type", sa.String(32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "last_used_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # Create indexes
    op.create_index(
        "ix_conversation_mappings_openai_id",
        "conversation_mappings",
        ["openai_conversation_id"],
    )
    op.create_index(
        "ix_conversation_mappings_org_team",
        "conversation_mappings",
        ["org_id", "team_node_id"],
    )
    op.create_index(
        "ix_conversation_mappings_type", "conversation_mappings", ["session_type"]
    )


def downgrade():
    op.drop_index("ix_conversation_mappings_type")
    op.drop_index("ix_conversation_mappings_org_team")
    op.drop_index("ix_conversation_mappings_openai_id")
    op.drop_table("conversation_mappings")
