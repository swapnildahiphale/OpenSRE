"""Investigation follow-up rows — channel delivery only (nudge timing,
identity, ConversationReference). Resolution state lives on the Neo4j
Episode, not here. See docs/superpowers/specs/2026-09-05-investigation-
resolution-follow-up-design.md §7.3."""

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import JSON, DateTime, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class InvestigationFollowup(Base):
    __tablename__ = "investigation_followups"

    correlation_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    org_id: Mapped[str] = mapped_column(String(64), nullable=False)
    team_node_id: Mapped[str] = mapped_column(String(128), nullable=False)
    entry_channel: Mapped[str] = mapped_column(String(16), nullable=False)  # "teams" | "web"
    trigger_actor_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    trigger_actor_teams_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    conversation_ref: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    # When set, timed follow-ups deliver on Jira (not Teams/Web).
    ticket_key: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    ticket_provider: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    nudge_due_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    nudge_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_nudge_text: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    stopped_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    __table_args__ = (
        Index(
            "ix_investigation_followups_due",
            "nudge_due_at",
            postgresql_where="stopped_at IS NULL",
        ),
        Index("ix_investigation_followups_team", "org_id", "team_node_id"),
    )
