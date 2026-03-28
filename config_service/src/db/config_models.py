"""
SQLAlchemy models for the hierarchical configuration system.

These are separate from the main models.py to keep things modular.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class NodeConfiguration(Base):
    """
    Stores configuration for a node in the org hierarchy.

    Each node (org, team, sub-team) has its own config that overrides parent.
    The effective_config_json is a cached computation of the merged config.
    """

    __tablename__ = "node_configurations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    org_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    node_id: Mapped[str] = mapped_column(String(128), nullable=False)
    node_type: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # 'org' or 'team'

    # The raw config overrides for this node (not merged)
    config_json: Mapped[dict] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False, default=dict
    )

    # Cached merged config (computed from hierarchy)
    effective_config_json: Mapped[Optional[dict]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    effective_config_computed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Audit
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )
    updated_by: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)

    __table_args__ = (
        UniqueConstraint("org_id", "node_id", name="uq_node_configurations_org_node"),
    )


class ConfigFieldDefinition(Base):
    """
    Metadata about configuration fields.

    Defines what fields exist, their types, whether they're required, etc.
    This is used for validation and UI generation.
    """

    __tablename__ = "config_field_definitions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    path: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    field_type: Mapped[str] = mapped_column(String(32), nullable=False)

    # Behavior
    required: Mapped[bool] = mapped_column(Boolean, default=False)
    default_value: Mapped[Optional[dict]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    locked_at_level: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=False)

    # Display
    display_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    example_value: Mapped[Optional[dict]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    placeholder: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)

    # Validation
    validation_regex: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    min_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    allowed_values: Mapped[Optional[list]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )

    # Categorization
    category: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, index=True
    )
    subcategory: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )


class ConfigValidationStatus(Base):
    """
    Tracks validation status for each node.

    Helps the UI show which teams have incomplete configuration.
    """

    __tablename__ = "config_validation_status"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    org_id: Mapped[str] = mapped_column(String(64), nullable=False)
    node_id: Mapped[str] = mapped_column(String(128), nullable=False)

    # Validation results
    missing_required_fields: Mapped[list] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=list
    )
    validation_errors: Mapped[list] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=list
    )
    is_valid: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    validated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )

    __table_args__ = (
        UniqueConstraint(
            "org_id", "node_id", name="uq_config_validation_status_org_node"
        ),
    )


class ConfigChangeHistory(Base):
    """
    History of configuration changes for audit and rollback.
    """

    __tablename__ = "config_change_history"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    org_id: Mapped[str] = mapped_column(String(64), nullable=False)
    node_id: Mapped[str] = mapped_column(String(128), nullable=False)

    # What changed
    previous_config: Mapped[Optional[dict]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    new_config: Mapped[dict] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False
    )
    change_diff: Mapped[Optional[dict]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )

    # Who/when
    changed_by: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    change_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Version number
    version: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        Index("ix_config_change_history_org_node", "org_id", "node_id"),
        Index("ix_config_change_history_changed_at", "changed_at"),
    )


class IntegrationSchema(Base):
    """
    Global integration schema definitions (not per-org).

    Defines available integrations like Coralogix, Snowflake, GitHub, etc.
    Each integration has a schema that describes what fields it needs.
    Actual credential values are stored in NodeConfiguration.integrations.
    """

    __tablename__ = "integration_schemas"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Documentation and display
    docs_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    icon_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=999)
    featured: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=True
    )

    # Field definitions as JSONB array
    # Format: [{"name": "api_key", "type": "secret", "required": true, "level": "org", ...}]
    fields: Mapped[list] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False, default=list
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )
