"""Consolidated schema for OpenSRE Config Service

Revision ID: 20260113_consolidated
Revises:
Create Date: 2026-01-13

This is the single consolidated migration containing all database schema.

Consolidates:
- 20260111_initial: Initial schema with 26 tables
- 20260113_fix_duration: Float type for duration_seconds
- 20260113_drop_legacy: No legacy tables created

All tables created in their final state. No legacy tables, no intermediate migrations.
For fresh deployments, this is the only migration needed.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260113_consolidated"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Core org/team hierarchy
    op.create_table(
        "org_nodes",
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column("node_id", sa.String(128), nullable=False),
        sa.Column("node_type", sa.String(32), nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("parent_id", sa.String(128), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("org_id", "node_id"),
    )
    op.create_index("ix_org_nodes_org_id", "org_nodes", ["org_id"])
    op.create_index("ix_org_nodes_parent_id", "org_nodes", ["parent_id"])

    # Authentication tables
    op.create_table(
        "team_tokens",
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column("team_node_id", sa.String(128), nullable=False),
        sa.Column("token_id", sa.String(128), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column(
            "issued_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("issued_by", sa.String(128), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "permissions",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text(
                '\'["config:read", "config:write", "agent:invoke"]\'::jsonb'
            ),
        ),
        sa.Column("label", sa.String(256), nullable=True),
        sa.PrimaryKeyConstraint("org_id", "team_node_id", "token_id"),
        sa.ForeignKeyConstraint(
            ["org_id", "team_node_id"],
            ["org_nodes.org_id", "org_nodes.node_id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_team_tokens_org_team", "team_tokens", ["org_id", "team_node_id"]
    )
    op.create_index("ix_team_tokens_token_hash", "team_tokens", ["token_hash"])

    op.create_table(
        "org_admin_tokens",
        sa.Column("token_id", sa.String(64), nullable=False),
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("name", sa.String(256), nullable=True),
        sa.Column("created_by", sa.String(256), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.PrimaryKeyConstraint("token_id"),
    )
    op.create_index("ix_org_admin_tokens_org_id", "org_admin_tokens", ["org_id"])
    op.create_index(
        "ix_org_admin_tokens_token_hash", "org_admin_tokens", ["token_hash"]
    )

    # Audit tables
    op.create_table(
        "token_audit",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("token_id", sa.String(64), nullable=False),
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column("team_node_id", sa.String(128), nullable=True),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("endpoint", sa.String(256), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_token_audit_token_id", "token_audit", ["token_id"])
    op.create_index("ix_token_audit_org_id", "token_audit", ["org_id"])
    op.create_index("ix_token_audit_created_at", "token_audit", ["created_at"])

    # Node configurations (hierarchical config system)
    op.create_table(
        "node_configurations",
        sa.Column("id", sa.String(64), nullable=False),
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column("node_id", sa.String(128), nullable=False),
        sa.Column("node_type", sa.String(32), nullable=False),
        sa.Column(
            "config_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "effective_config_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "effective_config_computed_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("updated_by", sa.String(128), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "org_id", "node_id", name="uq_node_configurations_org_node"
        ),
    )
    op.create_index("ix_node_configurations_org_id", "node_configurations", ["org_id"])

    op.create_table(
        "config_field_definitions",
        sa.Column("id", sa.String(64), nullable=False),
        sa.Column("path", sa.String(512), nullable=False, unique=True),
        sa.Column("field_type", sa.String(32), nullable=False),
        sa.Column(
            "required", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column(
            "default_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("locked_at_level", sa.String(32), nullable=True),
        sa.Column(
            "requires_approval",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("display_name", sa.String(128), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "example_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("placeholder", sa.String(256), nullable=True),
        sa.Column("validation_regex", sa.String(512), nullable=True),
        sa.Column("min_value", sa.Float(), nullable=True),
        sa.Column("max_value", sa.Float(), nullable=True),
        sa.Column(
            "allowed_values", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("category", sa.String(64), nullable=True),
        sa.Column("subcategory", sa.String(64), nullable=True),
        sa.Column(
            "sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "config_validation_status",
        sa.Column("id", sa.String(64), nullable=False),
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column("node_id", sa.String(128), nullable=False),
        sa.Column(
            "missing_required_fields",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "validation_errors",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "is_valid", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column(
            "validated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "node_id"),
    )

    op.create_table(
        "config_change_history",
        sa.Column("id", sa.String(64), nullable=False),
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column("node_id", sa.String(128), nullable=False),
        sa.Column(
            "previous_config", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column(
            "new_config", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "change_diff", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("changed_by", sa.String(128), nullable=True),
        sa.Column(
            "changed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("change_reason", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # Security and SSO
    op.create_table(
        "security_policies",
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column(
            "require_mfa", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("session_timeout_minutes", sa.Integer(), nullable=True),
        sa.Column(
            "allowed_ip_ranges", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("token_expiry_days", sa.Integer(), nullable=True),
        sa.Column(
            "require_approval_for_config_changes",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("updated_by", sa.String(256), nullable=True),
        sa.PrimaryKeyConstraint("org_id"),
    )

    op.create_table(
        "sso_configs",
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column(
            "enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("saml_metadata_url", sa.Text(), nullable=True),
        sa.Column("saml_entity_id", sa.String(256), nullable=True),
        sa.Column("oidc_client_id", sa.String(256), nullable=True),
        sa.Column("oidc_client_secret", sa.Text(), nullable=True),
        sa.Column("oidc_discovery_url", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("org_id"),
    )

    # Agent runs and sessions
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.String(64), nullable=False),
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column("team_node_id", sa.String(128), nullable=True),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.Column("trigger_source", sa.String(32), nullable=False),
        sa.Column("trigger_actor", sa.String(128), nullable=True),
        sa.Column("trigger_message", sa.Text(), nullable=True),
        sa.Column("trigger_channel_id", sa.String(64), nullable=True),
        sa.Column("agent_name", sa.String(64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("tool_calls_count", sa.Integer(), nullable=True),
        sa.Column("output_summary", sa.Text(), nullable=True),
        sa.Column(
            "output_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Integer(), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column(
            "extra_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_runs_org_id", "agent_runs", ["org_id"])
    op.create_index("ix_agent_runs_team_node_id", "agent_runs", ["team_node_id"])
    op.create_index("ix_agent_runs_started_at", "agent_runs", ["started_at"])
    op.create_index("ix_agent_runs_status", "agent_runs", ["status"])

    op.create_table(
        "agent_sessions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("investigation_id", sa.String(256), nullable=False, unique=True),
        sa.Column("sdk_session_id", sa.String(256), nullable=True),
        sa.Column("session_data", sa.Text(), nullable=True),
        sa.Column(
            "status", sa.String(32), nullable=False, server_default=sa.text("'active'")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("last_accessed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "message_count", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("total_cost_usd", sa.Numeric(10, 6), nullable=True),
        sa.Column(
            "session_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
    )
    op.create_index(
        "ix_agent_sessions_investigation_id", "agent_sessions", ["investigation_id"]
    )
    op.create_index("ix_agent_sessions_status", "agent_sessions", ["status"])

    # Knowledge base
    op.create_table(
        "knowledge_documents",
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column("team_node_id", sa.String(128), nullable=False),
        sa.Column("doc_id", sa.String(256), nullable=False),
        sa.Column("title", sa.String(512), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source_type", sa.String(64), nullable=True),
        sa.Column("source_id", sa.String(256), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("org_id", "team_node_id", "doc_id"),
        sa.ForeignKeyConstraint(
            ["org_id", "team_node_id"],
            ["org_nodes.org_id", "org_nodes.node_id"],
            ondelete="CASCADE",
        ),
    )

    op.create_table(
        "knowledge_edges",
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column("team_node_id", sa.String(128), nullable=False),
        sa.Column("entity", sa.String(256), nullable=False),
        sa.Column("relationship", sa.String(64), nullable=False),
        sa.Column("target", sa.String(256), nullable=False),
        sa.Column("source", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint(
            "org_id", "team_node_id", "entity", "relationship", "target"
        ),
        sa.ForeignKeyConstraint(
            ["org_id", "team_node_id"],
            ["org_nodes.org_id", "org_nodes.node_id"],
            ondelete="CASCADE",
        ),
    )

    # Workflow tables
    op.create_table(
        "pending_config_changes",
        sa.Column("change_id", sa.String(64), nullable=False),
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column("node_id", sa.String(128), nullable=False),
        sa.Column(
            "requested_config", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "change_diff", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("requested_by", sa.String(128), nullable=False),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("justification", sa.Text(), nullable=True),
        sa.Column(
            "status", sa.String(32), nullable=False, server_default=sa.text("'pending'")
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

    op.create_table(
        "pending_remediations",
        sa.Column("remediation_id", sa.String(64), nullable=False),
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column("team_node_id", sa.String(128), nullable=False),
        sa.Column("agent_run_id", sa.String(64), nullable=True),
        sa.Column("remediation_type", sa.String(64), nullable=False),
        sa.Column("target_service", sa.String(128), nullable=True),
        sa.Column("target_resource", sa.String(256), nullable=True),
        sa.Column(
            "action_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("justification", sa.Text(), nullable=True),
        sa.Column("risk_level", sa.String(32), nullable=True),
        sa.Column("requested_by", sa.String(128), nullable=False),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "status", sa.String(32), nullable=False, server_default=sa.text("'pending'")
        ),
        sa.Column("reviewed_by", sa.String(128), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_comment", sa.Text(), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "execution_result", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.PrimaryKeyConstraint("remediation_id"),
        sa.ForeignKeyConstraint(
            ["org_id", "team_node_id"],
            ["org_nodes.org_id", "org_nodes.node_id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_pending_remediations_org_team",
        "pending_remediations",
        ["org_id", "team_node_id"],
    )
    op.create_index(
        "ix_pending_remediations_status", "pending_remediations", ["status"]
    )

    # Integrations
    op.create_table(
        "integration_schemas",
        sa.Column("id", sa.String(64), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("docs_url", sa.String(512), nullable=True),
        sa.Column("icon_url", sa.String(512), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("featured", sa.Boolean(), nullable=False),
        sa.Column("fields", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "integrations",
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column("integration_id", sa.String(64), nullable=False),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'not_configured'"),
        ),
        sa.Column("display_name", sa.String(256), nullable=True),
        sa.Column(
            "config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("org_id", "integration_id"),
    )

    # Org settings
    op.create_table(
        "org_settings",
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column(
            "telemetry_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "usage_analytics_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "error_reporting_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "feature_flags",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("updated_by", sa.String(128), nullable=True),
        sa.PrimaryKeyConstraint("org_id"),
    )

    # Templates system
    op.create_table(
        "templates",
        sa.Column("template_id", sa.String(64), nullable=False),
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column("created_by_team_id", sa.String(128), nullable=True),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(64), nullable=True),
        sa.Column(
            "tags",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column(
            "template_config", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "is_public", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column(
            "is_featured", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("created_by", sa.String(128), nullable=True),
        sa.PrimaryKeyConstraint("template_id"),
    )
    op.create_index("ix_templates_org_id", "templates", ["org_id"])
    op.create_index("ix_templates_category", "templates", ["category"])
    op.create_index("ix_templates_is_public", "templates", ["is_public"])

    op.create_table(
        "template_applications",
        sa.Column("application_id", sa.String(64), nullable=False),
        sa.Column("template_id", sa.String(64), nullable=False),
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column("team_node_id", sa.String(128), nullable=False),
        sa.Column("applied_by", sa.String(128), nullable=True),
        sa.Column(
            "applied_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "applied_config", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("application_id"),
        sa.ForeignKeyConstraint(
            ["template_id"], ["templates.template_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["org_id", "team_node_id"],
            ["org_nodes.org_id", "org_nodes.node_id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_template_applications_template_id", "template_applications", ["template_id"]
    )
    op.create_index(
        "ix_template_applications_org_team",
        "template_applications",
        ["org_id", "team_node_id"],
    )

    op.create_table(
        "template_analytics",
        sa.Column("template_id", sa.String(64), nullable=False),
        sa.Column(
            "view_count", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "application_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("last_applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("template_id"),
        sa.ForeignKeyConstraint(
            ["template_id"], ["templates.template_id"], ondelete="CASCADE"
        ),
    )

    # Output configs (delivery & notifications)
    op.create_table(
        "team_output_configs",
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column("team_node_id", sa.String(128), nullable=False),
        sa.Column(
            "default_destinations",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "trigger_overrides", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("updated_by", sa.String(128), nullable=True),
        sa.PrimaryKeyConstraint("org_id", "team_node_id"),
        sa.ForeignKeyConstraint(
            ["org_id", "team_node_id"],
            ["org_nodes.org_id", "org_nodes.node_id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_team_output_configs_org_team",
        "team_output_configs",
        ["org_id", "team_node_id"],
    )

    # Impersonation tracking
    op.create_table(
        "impersonation_jtis",
        sa.Column("jti", sa.String(64), nullable=False),
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column("team_node_id", sa.String(128), nullable=False),
        sa.Column("subject", sa.String(256), nullable=True),
        sa.Column("email", sa.String(256), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("jti"),
        sa.ForeignKeyConstraint(
            ["org_id", "team_node_id"],
            ["org_nodes.org_id", "org_nodes.node_id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_impersonation_jtis_org_team",
        "impersonation_jtis",
        ["org_id", "team_node_id"],
    )
    op.create_index(
        "ix_impersonation_jtis_expires_at", "impersonation_jtis", ["expires_at"]
    )

    # Orchestrator provisioning
    op.create_table(
        "orchestrator_provisioning_runs",
        sa.Column("run_id", sa.String(64), nullable=False),
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column("team_node_id", sa.String(128), nullable=False),
        sa.Column("trigger_source", sa.String(32), nullable=False),
        sa.Column(
            "config_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("result_summary", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("run_id"),
    )
    op.create_index(
        "ix_orchestrator_provisioning_runs_org_team",
        "orchestrator_provisioning_runs",
        ["org_id", "team_node_id"],
    )
    op.create_index(
        "ix_orchestrator_provisioning_runs_status",
        "orchestrator_provisioning_runs",
        ["status"],
    )


def downgrade() -> None:
    # Drop all tables in reverse order to respect foreign key constraints
    op.drop_table("orchestrator_provisioning_runs")
    op.drop_table("impersonation_jtis")
    op.drop_table("team_output_configs")
    op.drop_table("template_analytics")
    op.drop_table("template_applications")
    op.drop_table("templates")
    op.drop_table("org_settings")
    op.drop_table("integrations")
    op.drop_table("integration_schemas")
    op.drop_table("pending_remediations")
    op.drop_table("pending_config_changes")
    op.drop_table("knowledge_edges")
    op.drop_table("knowledge_documents")
    op.drop_table("agent_sessions")
    op.drop_table("agent_runs")
    op.drop_table("sso_configs")
    op.drop_table("security_policies")
    op.drop_table("config_change_history")
    op.drop_table("config_validation_status")
    op.drop_table("config_field_definitions")
    op.drop_table("node_configurations")
    op.drop_table("node_config_audit")
    op.drop_table("token_audit")
    op.drop_table("org_admin_tokens")
    op.drop_table("team_tokens")
    op.drop_table("org_nodes")
