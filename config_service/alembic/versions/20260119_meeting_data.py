"""Add meeting_data table for storing meeting transcriptions

Revision ID: 20260119_meeting_data
Revises: 20260118_service_dependencies
Create Date: 2026-01-19

This migration adds a table to store meeting transcription data received from
webhook providers (Circleback) and API providers (Fireflies, Vexa, Otter).
Meeting data is used by agents to get context from incident-related meetings.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = "20260119_meeting_data"
down_revision = "20260118_service_dependencies"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "meeting_data",
        # Composite primary key: org + team + meeting_id
        sa.Column("org_id", sa.String(64), primary_key=True),
        sa.Column("team_node_id", sa.String(128), primary_key=True),
        sa.Column("meeting_id", sa.String(256), primary_key=True),
        # Meeting metadata
        sa.Column(
            "provider", sa.String(32), nullable=False
        ),  # circleback, fireflies, vexa, otter
        sa.Column("name", sa.String(512), nullable=True),
        sa.Column("meeting_url", sa.String(1024), nullable=True),
        sa.Column("duration_seconds", sa.Integer, nullable=True),
        sa.Column("meeting_time", sa.DateTime(timezone=True), nullable=True),
        # Participants
        sa.Column("attendees", JSONB, nullable=True),  # [{name, email}]
        # Content
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("transcript", JSONB, nullable=True),  # [{speaker, text, timestamp}]
        sa.Column("action_items", JSONB, nullable=True),  # [{title, assignee, status}]
        sa.Column("summary", JSONB, nullable=True),  # {overview, key_points, decisions}
        # Full raw payload for debugging
        sa.Column("raw_payload", JSONB, nullable=True),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # Indexes for common query patterns
    op.create_index(
        "ix_meeting_data_org_team",
        "meeting_data",
        ["org_id", "team_node_id"],
    )
    op.create_index(
        "ix_meeting_data_provider",
        "meeting_data",
        ["org_id", "team_node_id", "provider"],
    )
    op.create_index(
        "ix_meeting_data_time",
        "meeting_data",
        ["org_id", "team_node_id", "meeting_time"],
    )
    op.create_index(
        "ix_meeting_data_created",
        "meeting_data",
        ["org_id", "team_node_id", "created_at"],
    )


def downgrade():
    op.drop_index("ix_meeting_data_created")
    op.drop_index("ix_meeting_data_time")
    op.drop_index("ix_meeting_data_provider")
    op.drop_index("ix_meeting_data_org_team")
    op.drop_table("meeting_data")
