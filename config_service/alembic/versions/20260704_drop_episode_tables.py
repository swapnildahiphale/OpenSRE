"""Drop investigation_episodes and investigation_strategies tables.

Episodic memory has been moved from Postgres to Neo4j (neo4j-graphrag + fastembed).
These tables are no longer written to or read from by any service in this codebase.

DATA LOSS: This migration permanently destroys all rows in investigation_episodes
and investigation_strategies. There is no backfill to Neo4j — the data is
intentionally discarded. This project does not maintain backward compatibility
across storage backends. Neo4j is the authoritative episode store going forward.

If you are upgrading an existing installation and want to verify your exposure,
run these queries before applying this migration:

    SELECT COUNT(*) FROM investigation_episodes;
    SELECT COUNT(*) FROM investigation_strategies;

A count of 0 on both (fresh install, or already migrated to Neo4j) means no
historical data is at risk. Otherwise, decide whether to export rows before
running alembic upgrade head.

Revision ID: 20260704_drop_episode_tables
Revises: 20260702_tool_call_parent_id
Create Date: 2026-07-04
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "20260704_drop_episode_tables"
down_revision = "20260702_tool_call_parent_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_strategies_generated", table_name="investigation_strategies")
    op.drop_index("ix_strategies_lookup", table_name="investigation_strategies")
    op.drop_table("investigation_strategies")

    op.drop_index("ix_episodes_run_id", table_name="investigation_episodes")
    op.drop_index("ix_episodes_created_at", table_name="investigation_episodes")
    op.drop_index("ix_episodes_services", table_name="investigation_episodes")
    op.drop_index("ix_episodes_alert_type", table_name="investigation_episodes")
    op.drop_index("ix_episodes_team", table_name="investigation_episodes")
    op.drop_index("ix_episodes_org_id", table_name="investigation_episodes")
    op.drop_table("investigation_episodes")


def downgrade() -> None:
    op.create_table(
        "investigation_episodes",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("agent_run_id", sa.String(64), nullable=True),
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column("team_node_id", sa.String(128), nullable=True),
        sa.Column("alert_type", sa.String(128), nullable=True),
        sa.Column("alert_description", sa.Text, nullable=True),
        sa.Column("severity", sa.String(32), nullable=True),
        sa.Column("services", JSONB, nullable=True),
        sa.Column("agents_used", JSONB, nullable=True),
        sa.Column("skills_used", JSONB, nullable=True),
        sa.Column("key_findings", JSONB, nullable=True),
        sa.Column("resolved", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("root_cause", sa.Text, nullable=True),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("effectiveness_score", sa.Float, nullable=True),
        sa.Column("confidence", sa.Float, nullable=True),
        sa.Column("duration_seconds", sa.Float, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
    )
    op.create_index("ix_episodes_org_id", "investigation_episodes", ["org_id"])
    op.create_index(
        "ix_episodes_team", "investigation_episodes", ["org_id", "team_node_id"]
    )
    op.create_index("ix_episodes_alert_type", "investigation_episodes", ["alert_type"])
    op.create_index(
        "ix_episodes_services",
        "investigation_episodes",
        ["services"],
        postgresql_using="gin",
    )
    op.create_index("ix_episodes_created_at", "investigation_episodes", ["created_at"])
    op.create_index("ix_episodes_run_id", "investigation_episodes", ["agent_run_id"])

    op.create_table(
        "investigation_strategies",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column("team_node_id", sa.String(128), nullable=True),
        sa.Column("alert_type", sa.String(128), nullable=True),
        sa.Column("service_name", sa.String(128), nullable=True),
        sa.Column("strategy_text", sa.Text, nullable=False),
        sa.Column("source_episode_ids", JSONB, nullable=True),
        sa.Column("episode_count", sa.Integer, nullable=True),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_strategies_lookup",
        "investigation_strategies",
        ["org_id", "team_node_id", "alert_type", "service_name"],
    )
    op.create_index(
        "ix_strategies_generated", "investigation_strategies", ["generated_at"]
    )
