"""Investigation follow-up API — nudge delivery only.

Resolution state lives on the Neo4j Episode. These routes manage the
Postgres delivery row (timing, Teams ConversationReference, Web nudge text).

See design §7.3–7.6 and implementation plan Task 2.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...db.investigation_followups import InvestigationFollowup
from ...db.session import get_db
from ..auth import TeamPrincipal, require_team_auth
from .internal import require_internal_service

logger = structlog.get_logger(__name__)

# Cadence: silence windows measured from last activity / last nudge.
# window(n) for nudge_count n before the next fire: 30m, 3h, then 24h forever.
# TEMP for manual test — revert to 30m / 3h / 24h before merge
_WINDOW = {
    0: timedelta(minutes=1),
    1: timedelta(minutes=2),
    2: timedelta(minutes=3),
}


def window(nudge_count: int) -> timedelta:
    """Return silence window before the next nudge/abandon check."""
    return _WINDOW.get(nudge_count, _WINDOW[2])


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt is not None else None


def _to_dict(row: InvestigationFollowup) -> dict[str, Any]:
    return {
        "correlation_id": row.correlation_id,
        "org_id": row.org_id,
        "team_node_id": row.team_node_id,
        "entry_channel": row.entry_channel,
        "trigger_actor_name": row.trigger_actor_name,
        "trigger_actor_teams_id": row.trigger_actor_teams_id,
        "conversation_ref": row.conversation_ref,
        "ticket_key": row.ticket_key,
        "ticket_provider": row.ticket_provider,
        "nudge_due_at": _iso(row.nudge_due_at),
        "nudge_count": row.nudge_count,
        "last_nudge_text": row.last_nudge_text,
        "stopped_at": _iso(row.stopped_at),
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
    }


# =============================================================================
# Request bodies
# =============================================================================


class UpsertFollowupRequest(BaseModel):
    correlation_id: str = Field(..., max_length=255)
    org_id: str = Field(..., max_length=64)
    team_node_id: str = Field(..., max_length=128)
    entry_channel: str = Field(..., max_length=16)  # teams | web
    trigger_actor_name: Optional[str] = Field(None, max_length=128)
    trigger_actor_teams_id: Optional[str] = Field(None, max_length=128)
    conversation_ref: Optional[dict[str, Any]] = None
    ticket_key: Optional[str] = Field(None, max_length=64)
    ticket_provider: Optional[str] = Field(None, max_length=32)
    # Caller (sre-agent) computes from Episode.resolution_status == "open"
    still_open: bool = True


class NudgeSentRequest(BaseModel):
    last_nudge_text: Optional[str] = Field(None, max_length=1024)


class AttachTicketRequest(BaseModel):
    ticket_key: str = Field(..., max_length=64)
    ticket_provider: str = Field(default="jira", max_length=32)


# =============================================================================
# Internal routes (opensre-scheduler / sre-agent)
# =============================================================================

internal_router = APIRouter(
    prefix="/api/v1/internal/investigation-followups",
    tags=["internal-investigation-followups"],
)


@internal_router.get("/due")
async def get_due_followups(
    limit: int = 10,
    db: Session = Depends(get_db),
    caller: str = Depends(require_internal_service),
):
    """Claim due, unstopped followup rows (FOR UPDATE SKIP LOCKED).

    A row is due when nudge_due_at <= now AND stopped_at IS NULL.
    No channel filter — Teams and Web are claimed identically.
    """
    now = _now()
    rows = (
        db.execute(
            select(InvestigationFollowup)
            .where(
                InvestigationFollowup.nudge_due_at <= now,
                InvestigationFollowup.stopped_at.is_(None),
            )
            .order_by(InvestigationFollowup.nudge_due_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        .scalars()
        .all()
    )
    # No separate claimed_at — dispatch always advances nudge_due_at or
    # sets stopped_at before the transaction releases, so a concurrent
    # poller cannot see the same row again until that write commits.
    result = [_to_dict(r) for r in rows]
    db.commit()
    logger.info(
        "investigation_followups_due",
        count=len(result),
        caller=caller,
    )
    return {"followups": result, "count": len(result)}


@internal_router.post("/upsert")
async def upsert_followup(
    body: UpsertFollowupRequest,
    db: Session = Depends(get_db),
    caller: str = Depends(require_internal_service),
):
    """Create-or-touch a followup row (reset_on_activity).

    First call: insert with nudge_count=0, nudge_due_at = now + window(0).
    Later calls: if still_open, restart the clock at Follow-up 1 of 3 —
    nudge_count=0, clear last_nudge_text, nudge_due_at = now + window(0).
    Reopens abandoned rows (clears stopped_at) when the human continues
    an still-open investigation.
    """
    row = db.get(InvestigationFollowup, body.correlation_id)
    now = _now()

    if row is None:
        row = InvestigationFollowup(
            correlation_id=body.correlation_id,
            org_id=body.org_id,
            team_node_id=body.team_node_id,
            entry_channel=body.entry_channel,
            trigger_actor_name=body.trigger_actor_name,
            trigger_actor_teams_id=body.trigger_actor_teams_id,
            conversation_ref=body.conversation_ref,
            ticket_key=body.ticket_key,
            ticket_provider=body.ticket_provider if body.ticket_key else None,
            nudge_count=0,
            nudge_due_at=now + window(0),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        logger.info(
            "investigation_followup_created",
            correlation_id=row.correlation_id,
            caller=caller,
        )
        return _to_dict(row)

    # Existing row — optionally refresh identity / conversation_ref
    if body.trigger_actor_name and not row.trigger_actor_name:
        row.trigger_actor_name = body.trigger_actor_name
    if body.trigger_actor_teams_id and not row.trigger_actor_teams_id:
        row.trigger_actor_teams_id = body.trigger_actor_teams_id
    if body.conversation_ref is not None:
        row.conversation_ref = body.conversation_ref
    if body.ticket_key:
        row.ticket_key = body.ticket_key.strip().upper()
        row.ticket_provider = (body.ticket_provider or "jira").strip().lower()

    if body.still_open:
        # Human activity restarts the follow-up series at 1 of 3.
        row.stopped_at = None
        row.nudge_count = 0
        row.last_nudge_text = None
        row.nudge_due_at = now + window(0)

    db.commit()
    db.refresh(row)
    return _to_dict(row)


@internal_router.post("/{correlation_id}/attach-ticket")
async def attach_ticket(
    correlation_id: str,
    body: AttachTicketRequest,
    db: Session = Depends(get_db),
    caller: str = Depends(require_internal_service),
):
    """Bind a Jira key and restart follow-ups on that ticket (1 of 3)."""
    row = db.get(InvestigationFollowup, correlation_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Followup not found")

    key = body.ticket_key.strip().upper()
    if not key:
        raise HTTPException(status_code=400, detail="ticket_key required")

    now = _now()
    row.ticket_key = key
    row.ticket_provider = (body.ticket_provider or "jira").strip().lower() or "jira"
    # Switching delivery to Jira always restarts the cadence at 1 of 3.
    row.stopped_at = None
    row.nudge_count = 0
    row.last_nudge_text = None
    row.nudge_due_at = now + window(0)
    db.commit()
    db.refresh(row)
    logger.info(
        "investigation_followup_ticket_attached",
        correlation_id=correlation_id,
        ticket_key=row.ticket_key,
        caller=caller,
    )
    return _to_dict(row)


@internal_router.post("/{correlation_id}/abandon")
async def abandon_followup(
    correlation_id: str,
    db: Session = Depends(get_db),
    caller: str = Depends(require_internal_service),
):
    """Set stopped_at = now. Idempotent. Also used to cancel after confirm."""
    row = db.get(InvestigationFollowup, correlation_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Followup not found")

    if row.stopped_at is None:
        row.stopped_at = _now()
        db.commit()
        db.refresh(row)
        logger.info(
            "investigation_followup_stopped",
            correlation_id=correlation_id,
            caller=caller,
        )
    return _to_dict(row)


@internal_router.post("/{correlation_id}/nudge-sent")
async def record_nudge_sent(
    correlation_id: str,
    body: NudgeSentRequest,
    db: Session = Depends(get_db),
    caller: str = Depends(require_internal_service),
):
    """Record that a nudge was delivered: bump nudge_count, set next due."""
    row = db.get(InvestigationFollowup, correlation_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Followup not found")
    if row.stopped_at is not None:
        raise HTTPException(status_code=409, detail="Followup already stopped")

    row.nudge_count = int(row.nudge_count or 0) + 1
    if body.last_nudge_text is not None:
        row.last_nudge_text = body.last_nudge_text
    row.nudge_due_at = _now() + window(row.nudge_count)
    db.commit()
    db.refresh(row)
    logger.info(
        "investigation_followup_nudge_sent",
        correlation_id=correlation_id,
        nudge_count=row.nudge_count,
        caller=caller,
    )
    return _to_dict(row)


@internal_router.post("/{correlation_id}/reschedule")
async def reschedule_followup(
    correlation_id: str,
    db: Session = Depends(get_db),
    caller: str = Depends(require_internal_service),
):
    """Push nudge_due_at forward without changing nudge_count (soft-defer)."""
    row = db.get(InvestigationFollowup, correlation_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Followup not found")
    if row.stopped_at is not None:
        raise HTTPException(status_code=409, detail="Followup already stopped")

    row.nudge_due_at = _now() + window(int(row.nudge_count or 0))
    db.commit()
    db.refresh(row)
    logger.info(
        "investigation_followup_rescheduled",
        correlation_id=correlation_id,
        nudge_count=row.nudge_count,
        caller=caller,
    )
    return _to_dict(row)


# =============================================================================
# Team-facing routes (web_ui)
# =============================================================================

team_router = APIRouter(
    prefix="/api/v1/team/investigation-followups",
    tags=["team-investigation-followups"],
)


@team_router.get("/{correlation_id}")
async def get_team_followup(
    correlation_id: str,
    db: Session = Depends(get_db),
    team: TeamPrincipal = Depends(require_team_auth),
):
    """Delivery status for Web badge/banner. Never returns conversation_ref."""
    row = db.execute(
        select(InvestigationFollowup).where(
            InvestigationFollowup.correlation_id == correlation_id,
            InvestigationFollowup.org_id == team.org_id,
            InvestigationFollowup.team_node_id == team.team_node_id,
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Followup not found")
    return {
        "correlation_id": row.correlation_id,
        "nudge_count": row.nudge_count,
        "last_nudge_text": row.last_nudge_text,
        "stopped_at": _iso(row.stopped_at),
        "ticket_key": row.ticket_key,
        "ticket_provider": row.ticket_provider,
    }
