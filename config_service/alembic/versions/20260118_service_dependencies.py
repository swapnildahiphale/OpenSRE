"""Add service_dependencies and dependency_discovery_runs tables

Revision ID: 20260118_service_dependencies
Revises: 20260118_conversation_mappings
Create Date: 2026-01-18

This migration adds tables for the service dependency discovery system:
- service_dependencies: Stores discovered service-to-service dependencies
- dependency_discovery_runs: Tracks discovery job executions

The dependency service discovers these relationships from observability
platforms (New Relic, Datadog, CloudWatch, Prometheus) and stores them
for agent querying during incident triage.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, JSON, UUID

# revision identifiers, used by Alembic.
revision = "20260118_service_dependencies"
down_revision = "20260118_conversation_mappings"
branch_labels = None
depends_on = None


def upgrade():
    # Service Dependencies table - stores discovered service relationships
    op.create_table(
        "service_dependencies",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("team_id", sa.String(128), nullable=False),
        sa.Column("source_service", sa.String(200), nullable=False),
        sa.Column("target_service", sa.String(200), nullable=False),
        sa.Column("call_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("avg_duration_ms", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("error_rate", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("confidence", sa.Float, nullable=False, server_default="0.0"),
        sa.Column(
            "evidence_sources",
            ARRAY(sa.String),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("evidence_metadata", JSON, nullable=False, server_default="{}"),
        sa.Column(
            "discovered_at",
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
        # Unique constraint for upsert
        sa.UniqueConstraint(
            "team_id",
            "source_service",
            "target_service",
            name="uq_service_dependency_edge",
        ),
    )

    # Indexes for service_dependencies
    op.create_index(
        "ix_service_dependencies_team_id",
        "service_dependencies",
        ["team_id"],
    )
    op.create_index(
        "ix_service_dependencies_source",
        "service_dependencies",
        ["team_id", "source_service"],
    )
    op.create_index(
        "ix_service_dependencies_target",
        "service_dependencies",
        ["team_id", "target_service"],
    )
    op.create_index(
        "ix_service_dependencies_updated",
        "service_dependencies",
        ["team_id", "updated_at"],
    )

    # Discovery Runs table - tracks job executions
    op.create_table(
        "dependency_discovery_runs",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("team_id", sa.String(128), nullable=False),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="'queued'",
        ),
        sa.Column("config_snapshot", JSON, nullable=False, server_default="{}"),
        sa.Column("sources_queried", ARRAY(sa.String), nullable=True),
        sa.Column("services_discovered", sa.Integer, nullable=True),
        sa.Column("dependencies_discovered", sa.Integer, nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Indexes for discovery_runs
    op.create_index(
        "ix_discovery_runs_team_id",
        "dependency_discovery_runs",
        ["team_id"],
    )
    op.create_index(
        "ix_discovery_runs_status",
        "dependency_discovery_runs",
        ["team_id", "status"],
    )
    op.create_index(
        "ix_discovery_runs_created",
        "dependency_discovery_runs",
        ["team_id", "created_at"],
    )


def downgrade():
    # Drop discovery_runs indexes and table
    op.drop_index("ix_discovery_runs_created")
    op.drop_index("ix_discovery_runs_status")
    op.drop_index("ix_discovery_runs_team_id")
    op.drop_table("dependency_discovery_runs")

    # Drop service_dependencies indexes and table
    op.drop_index("ix_service_dependencies_updated")
    op.drop_index("ix_service_dependencies_target")
    op.drop_index("ix_service_dependencies_source")
    op.drop_index("ix_service_dependencies_team_id")
    op.drop_table("service_dependencies")
