"""
Unified Audit API - Aggregates events from tokens, config, and agent runs.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.auth import AdminPrincipal, authenticate_admin_request
from src.db import repository
from src.db.session import db_session

router = APIRouter(prefix="/unified-audit", tags=["Unified Audit"])


def require_admin(
    principal: AdminPrincipal = Depends(authenticate_admin_request),
) -> AdminPrincipal:
    return principal


def get_db() -> Session:
    with db_session() as s:
        yield s


class AuditEventResponse(BaseModel):
    """Single audit event in unified format."""

    id: str
    source: str
    event_type: str
    timestamp: datetime
    actor: Optional[str]
    team_node_id: Optional[str]
    team_name: Optional[str] = None
    summary: str
    details: Dict[str, Any]
    correlation_id: Optional[str] = None


class AuditListResponse(BaseModel):
    """Paginated list of audit events."""

    events: List[AuditEventResponse]
    total: int
    limit: int
    offset: int
    has_more: bool


class AgentRunCreateRequest(BaseModel):
    """Request to create an agent run record."""

    run_id: str
    org_id: str
    team_node_id: Optional[str] = None
    correlation_id: Optional[str] = None
    trigger_source: str
    trigger_actor: Optional[str] = None
    trigger_message: Optional[str] = None
    trigger_channel_id: Optional[str] = None
    agent_name: str
    metadata: Optional[Dict[str, Any]] = None


class AgentRunCompleteRequest(BaseModel):
    """Request to mark an agent run as complete."""

    run_id: str
    status: str = Field(..., pattern="^(completed|failed|timeout)$")
    tool_calls_count: Optional[int] = None
    output_summary: Optional[str] = None
    output_json: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    confidence: Optional[int] = None


class AgentRunResponse(BaseModel):
    """Agent run response."""

    id: str
    org_id: str
    team_node_id: Optional[str]
    correlation_id: Optional[str]
    trigger_source: str
    trigger_actor: Optional[str]
    trigger_message: Optional[str]
    agent_name: str
    status: str
    started_at: datetime
    completed_at: Optional[datetime]
    tool_calls_count: Optional[int]
    output_summary: Optional[str]
    confidence: Optional[int]
    duration_seconds: Optional[float]
    error_message: Optional[str]


@router.get("", response_model=AuditListResponse)
def list_unified_audit(
    org_id: str,
    sources: Optional[str] = Query(
        None, description="Comma-separated: token,config,agent"
    ),
    team_node_id: Optional[str] = Query(None),
    event_types: Optional[str] = Query(None, description="Comma-separated event types"),
    actor: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    since: Optional[datetime] = Query(None),
    until: Optional[datetime] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_db),
    admin: AdminPrincipal = Depends(require_admin),
):
    """
    Get unified audit log across all sources.

    Sources:
    - token: Token lifecycle events (issued, revoked, expired, permission_denied)
    - config: Configuration changes
    - agent: Agent run records
    """
    source_list = sources.split(",") if sources else None
    event_type_list = event_types.split(",") if event_types else None

    events, total = repository.list_unified_audit(
        session,
        org_id=org_id,
        sources=source_list,
        team_node_id=team_node_id,
        event_types=event_type_list,
        actor=actor,
        search=search,
        since=since,
        until=until,
        limit=limit,
        offset=offset,
    )

    # Build team name lookup for better display
    nodes = {n.node_id: n for n in repository.list_org_nodes(session, org_id=org_id)}

    response_events = []
    for e in events:
        team_name = None
        if e.team_node_id and e.team_node_id in nodes:
            team_name = nodes[e.team_node_id].name or e.team_node_id

        response_events.append(
            AuditEventResponse(
                id=e.id,
                source=e.source,
                event_type=e.event_type,
                timestamp=e.timestamp,
                actor=e.actor,
                team_node_id=e.team_node_id,
                team_name=team_name,
                summary=e.summary,
                details=e.details,
                correlation_id=e.correlation_id,
            )
        )

    return AuditListResponse(
        events=response_events,
        total=total,
        limit=limit,
        offset=offset,
        has_more=offset + limit < total,
    )


@router.get("/export")
def export_audit_csv(
    org_id: str,
    sources: Optional[str] = Query(None),
    team_node_id: Optional[str] = Query(None),
    event_types: Optional[str] = Query(None),
    actor: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    since: Optional[datetime] = Query(None),
    until: Optional[datetime] = Query(None),
    session: Session = Depends(get_db),
    admin: AdminPrincipal = Depends(require_admin),
):
    """Export audit log as CSV for compliance reporting."""
    source_list = sources.split(",") if sources else None
    event_type_list = event_types.split(",") if event_types else None

    events, _ = repository.list_unified_audit(
        session,
        org_id=org_id,
        sources=source_list,
        team_node_id=team_node_id,
        event_types=event_type_list,
        actor=actor,
        search=search,
        since=since,
        until=until,
        limit=10000,  # Max export
        offset=0,
    )

    # Build CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "Timestamp",
            "Source",
            "Event Type",
            "Actor",
            "Team",
            "Summary",
            "Correlation ID",
        ]
    )

    for e in events:
        writer.writerow(
            [
                e.timestamp.isoformat(),
                e.source,
                e.event_type,
                e.actor or "",
                e.team_node_id or "",
                e.summary,
                e.correlation_id or "",
            ]
        )

    csv_content = output.getvalue()

    filename = (
        f"audit_export_{org_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    )

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# --- Agent Run Recording (for orchestrator to call) ---


@router.post("/agent-runs", response_model=AgentRunResponse)
def create_agent_run(
    request: AgentRunCreateRequest,
    session: Session = Depends(get_db),
    admin: AdminPrincipal = Depends(require_admin),
):
    """Create a new agent run record (called by orchestrator at run start)."""
    run = repository.create_agent_run(
        session,
        run_id=request.run_id,
        org_id=request.org_id,
        team_node_id=request.team_node_id,
        correlation_id=request.correlation_id,
        trigger_source=request.trigger_source,
        trigger_actor=request.trigger_actor,
        trigger_message=request.trigger_message,
        trigger_channel_id=request.trigger_channel_id,
        agent_name=request.agent_name,
        metadata=request.metadata,
    )
    session.commit()

    return AgentRunResponse(
        id=run.id,
        org_id=run.org_id,
        team_node_id=run.team_node_id,
        correlation_id=run.correlation_id,
        trigger_source=run.trigger_source,
        trigger_actor=run.trigger_actor,
        trigger_message=run.trigger_message,
        agent_name=run.agent_name,
        status=run.status,
        started_at=run.started_at,
        completed_at=run.completed_at,
        tool_calls_count=run.tool_calls_count,
        output_summary=run.output_summary,
        confidence=run.confidence,
        duration_seconds=run.duration_seconds,
        error_message=run.error_message,
    )


@router.patch("/agent-runs/{run_id}", response_model=AgentRunResponse)
def complete_agent_run(
    run_id: str,
    request: AgentRunCompleteRequest,
    session: Session = Depends(get_db),
    admin: AdminPrincipal = Depends(require_admin),
):
    """Mark an agent run as complete (called by orchestrator when run finishes)."""
    run = repository.complete_agent_run(
        session,
        run_id=run_id,
        status=request.status,
        tool_calls_count=request.tool_calls_count,
        output_summary=request.output_summary,
        output_json=request.output_json,
        error_message=request.error_message,
        confidence=request.confidence,
    )

    if run is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Agent run not found")

    session.commit()

    return AgentRunResponse(
        id=run.id,
        org_id=run.org_id,
        team_node_id=run.team_node_id,
        correlation_id=run.correlation_id,
        trigger_source=run.trigger_source,
        trigger_actor=run.trigger_actor,
        trigger_message=run.trigger_message,
        agent_name=run.agent_name,
        status=run.status,
        started_at=run.started_at,
        completed_at=run.completed_at,
        tool_calls_count=run.tool_calls_count,
        output_summary=run.output_summary,
        confidence=run.confidence,
        duration_seconds=run.duration_seconds,
        error_message=run.error_message,
    )


@router.get("/agent-runs", response_model=List[AgentRunResponse])
def list_agent_runs(
    org_id: str,
    team_node_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    trigger_source: Optional[str] = Query(None),
    agent_name: Optional[str] = Query(None),
    since: Optional[datetime] = Query(None),
    until: Optional[datetime] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_db),
    admin: AdminPrincipal = Depends(require_admin),
):
    """List agent runs with filtering."""
    runs = repository.list_agent_runs(
        session,
        org_id=org_id,
        team_node_id=team_node_id,
        status=status,
        trigger_source=trigger_source,
        agent_name=agent_name,
        since=since,
        until=until,
        limit=limit,
        offset=offset,
    )

    return [
        AgentRunResponse(
            id=run.id,
            org_id=run.org_id,
            team_node_id=run.team_node_id,
            correlation_id=run.correlation_id,
            trigger_source=run.trigger_source,
            trigger_actor=run.trigger_actor,
            trigger_message=run.trigger_message,
            agent_name=run.agent_name,
            status=run.status,
            started_at=run.started_at,
            completed_at=run.completed_at,
            tool_calls_count=run.tool_calls_count,
            output_summary=run.output_summary,
            confidence=run.confidence,
            duration_seconds=run.duration_seconds,
            error_message=run.error_message,
        )
        for run in runs
    ]
