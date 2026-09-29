"""Tests for investigation-followups internal + team routes."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.api.auth import TeamPrincipal, require_team_auth
from src.api.routes.investigation_followups import (
    internal_router,
    team_router,
    window,
)
from src.db.investigation_followups import InvestigationFollowup
from src.db.session import get_db


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    InvestigationFollowup.__table__.create(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    with SessionLocal() as s:
        yield s


@pytest.fixture()
def client(db_session):
    app = FastAPI()
    app.include_router(internal_router)
    app.include_router(team_router)

    def override_get_db():
        yield db_session

    def override_team_auth():
        return TeamPrincipal(
            auth_kind="team_token",
            org_id="local",
            team_node_id="default",
            subject="tester",
        )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_team_auth] = override_team_auth
    return TestClient(app)


def _headers():
    return {"X-Internal-Service": "opensre-scheduler"}


def test_window_boundaries():
    assert window(0) == timedelta(minutes=1)
    assert window(1) == timedelta(minutes=2)
    assert window(2) == timedelta(minutes=3)
    assert window(3) == timedelta(minutes=3)
    assert window(99) == timedelta(minutes=3)


def test_due_requires_internal_header(client):
    resp = client.get("/api/v1/internal/investigation-followups/due")
    assert resp.status_code == 401


def test_due_returns_only_past_due_unstopped(client, db_session):
    now = datetime.now(timezone.utc)
    db_session.add_all(
        [
            InvestigationFollowup(
                correlation_id="due-1",
                org_id="local",
                team_node_id="default",
                entry_channel="web",
                nudge_due_at=now - timedelta(minutes=1),
            ),
            InvestigationFollowup(
                correlation_id="future",
                org_id="local",
                team_node_id="default",
                entry_channel="web",
                nudge_due_at=now + timedelta(hours=1),
            ),
            InvestigationFollowup(
                correlation_id="stopped",
                org_id="local",
                team_node_id="default",
                entry_channel="teams",
                nudge_due_at=now - timedelta(minutes=1),
                stopped_at=now,
            ),
        ]
    )
    db_session.commit()

    resp = client.get(
        "/api/v1/internal/investigation-followups/due",
        headers=_headers(),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    assert body["followups"][0]["correlation_id"] == "due-1"
    assert body["followups"][0]["entry_channel"] == "web"


def test_upsert_creates_then_resets_when_still_open(client, db_session):
    resp = client.post(
        "/api/v1/internal/investigation-followups/upsert",
        headers=_headers(),
        json={
            "correlation_id": "thread-a",
            "org_id": "local",
            "team_node_id": "default",
            "entry_channel": "teams",
            "trigger_actor_name": "Jane",
            "trigger_actor_teams_id": "29:abc",
            "still_open": True,
        },
    )
    assert resp.status_code == 200
    created = resp.json()
    assert created["correlation_id"] == "thread-a"
    assert created["nudge_count"] == 0
    assert created["nudge_due_at"] is not None
    first_due = datetime.fromisoformat(created["nudge_due_at"])

    row = db_session.get(InvestigationFollowup, "thread-a")
    # Simulate mid-series nudges so reset-to-zero is observable.
    row.nudge_count = 2
    row.last_nudge_text = "Follow-up 2 of 3"
    row.nudge_due_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    db_session.commit()

    resp2 = client.post(
        "/api/v1/internal/investigation-followups/upsert",
        headers=_headers(),
        json={
            "correlation_id": "thread-a",
            "org_id": "local",
            "team_node_id": "default",
            "entry_channel": "teams",
            "still_open": True,
        },
    )
    assert resp2.status_code == 200
    body2 = resp2.json()
    second_due = datetime.fromisoformat(body2["nudge_due_at"])
    assert second_due > first_due - timedelta(minutes=1)
    assert body2["nudge_count"] == 0
    assert body2["last_nudge_text"] is None
    assert body2["stopped_at"] is None


def test_upsert_reopens_abandoned_on_activity(client, db_session):
    client.post(
        "/api/v1/internal/investigation-followups/upsert",
        headers=_headers(),
        json={
            "correlation_id": "thread-reopen",
            "org_id": "local",
            "team_node_id": "default",
            "entry_channel": "web",
            "still_open": True,
        },
    )
    client.post(
        "/api/v1/internal/investigation-followups/thread-reopen/abandon",
        headers=_headers(),
    )
    row = db_session.get(InvestigationFollowup, "thread-reopen")
    row.nudge_count = 3
    db_session.commit()

    resp = client.post(
        "/api/v1/internal/investigation-followups/upsert",
        headers=_headers(),
        json={
            "correlation_id": "thread-reopen",
            "org_id": "local",
            "team_node_id": "default",
            "entry_channel": "web",
            "still_open": True,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["stopped_at"] is None
    assert body["nudge_count"] == 0


def test_upsert_noop_when_not_still_open(client, db_session):
    client.post(
        "/api/v1/internal/investigation-followups/upsert",
        headers=_headers(),
        json={
            "correlation_id": "thread-b",
            "org_id": "local",
            "team_node_id": "default",
            "entry_channel": "web",
            "still_open": True,
        },
    )
    row = db_session.get(InvestigationFollowup, "thread-b")
    frozen = row.nudge_due_at

    resp = client.post(
        "/api/v1/internal/investigation-followups/upsert",
        headers=_headers(),
        json={
            "correlation_id": "thread-b",
            "org_id": "local",
            "team_node_id": "default",
            "entry_channel": "web",
            "still_open": False,
        },
    )
    assert resp.status_code == 200
    db_session.refresh(row)
    assert row.nudge_due_at == frozen


def test_abandon_sets_stopped_at_idempotent(client, db_session):
    client.post(
        "/api/v1/internal/investigation-followups/upsert",
        headers=_headers(),
        json={
            "correlation_id": "thread-c",
            "org_id": "local",
            "team_node_id": "default",
            "entry_channel": "web",
            "still_open": True,
        },
    )
    resp = client.post(
        "/api/v1/internal/investigation-followups/thread-c/abandon",
        headers=_headers(),
    )
    assert resp.status_code == 200
    assert resp.json()["stopped_at"] is not None
    first_stopped = resp.json()["stopped_at"]

    resp2 = client.post(
        "/api/v1/internal/investigation-followups/thread-c/abandon",
        headers=_headers(),
    )
    assert resp2.status_code == 200
    assert resp2.json()["stopped_at"] == first_stopped


def test_nudge_sent_advances_count_and_due(client, db_session):
    client.post(
        "/api/v1/internal/investigation-followups/upsert",
        headers=_headers(),
        json={
            "correlation_id": "thread-d",
            "org_id": "local",
            "team_node_id": "default",
            "entry_channel": "web",
            "still_open": True,
        },
    )
    resp = client.post(
        "/api/v1/internal/investigation-followups/thread-d/nudge-sent",
        headers=_headers(),
        json={"last_nudge_text": "Has this been fixed yet?"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["nudge_count"] == 1
    assert body["last_nudge_text"] == "Has this been fixed yet?"
    assert body["nudge_due_at"] is not None


def test_reschedule_pushes_due_without_count(client, db_session):
    client.post(
        "/api/v1/internal/investigation-followups/upsert",
        headers=_headers(),
        json={
            "correlation_id": "thread-rs",
            "org_id": "local",
            "team_node_id": "default",
            "entry_channel": "web",
            "still_open": True,
        },
    )
    row = db_session.get(InvestigationFollowup, "thread-rs")
    row.nudge_count = 1
    row.last_nudge_text = "Follow-up 1 of 3"
    row.nudge_due_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db_session.commit()
    before = row.nudge_due_at

    resp = client.post(
        "/api/v1/internal/investigation-followups/thread-rs/reschedule",
        headers=_headers(),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["nudge_count"] == 1
    assert body["last_nudge_text"] == "Follow-up 1 of 3"
    assert datetime.fromisoformat(body["nudge_due_at"]) > before


def test_team_read_excludes_conversation_ref(client, db_session):
    client.post(
        "/api/v1/internal/investigation-followups/upsert",
        headers=_headers(),
        json={
            "correlation_id": "thread-e",
            "org_id": "local",
            "team_node_id": "default",
            "entry_channel": "teams",
            "conversation_ref": {
                "conversation_id": "19:abc",
                "service_url": "https://example/",
            },
            "still_open": True,
        },
    )
    client.post(
        "/api/v1/internal/investigation-followups/thread-e/nudge-sent",
        headers=_headers(),
        json={"last_nudge_text": "Nudge text"},
    )

    resp = client.get("/api/v1/team/investigation-followups/thread-e")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {
        "correlation_id",
        "nudge_count",
        "last_nudge_text",
        "stopped_at",
        "ticket_key",
        "ticket_provider",
    }
    assert "conversation_ref" not in body
    assert body["last_nudge_text"] == "Nudge text"
    assert body["nudge_count"] == 1
    assert body["ticket_key"] is None


def test_attach_ticket(client, db_session):
    client.post(
        "/api/v1/internal/investigation-followups/upsert",
        headers=_headers(),
        json={
            "correlation_id": "thread-ticket",
            "org_id": "local",
            "team_node_id": "default",
            "entry_channel": "web",
            "still_open": True,
        },
    )
    # Mid-flight: two web nudges already sent.
    row = db_session.get(InvestigationFollowup, "thread-ticket")
    row.nudge_count = 2
    row.last_nudge_text = "Follow-up 2 of 3"
    db_session.commit()

    resp = client.post(
        "/api/v1/internal/investigation-followups/thread-ticket/attach-ticket",
        headers=_headers(),
        json={"ticket_key": "proj-123", "ticket_provider": "jira"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ticket_key"] == "PROJ-123"
    assert body["ticket_provider"] == "jira"
    assert body["nudge_count"] == 0
    assert body["last_nudge_text"] is None
    assert body["stopped_at"] is None
    assert body["nudge_due_at"] is not None

    due = client.get(
        "/api/v1/internal/investigation-followups/due",
        headers=_headers(),
    )
    # not due yet (window in future) — just ensure serialize includes ticket on get via attach
    assert due.status_code == 200


def test_team_read_404_other_team(client, db_session):
    db_session.add(
        InvestigationFollowup(
            correlation_id="other-team",
            org_id="other-org",
            team_node_id="other-team",
            entry_channel="web",
        )
    )
    db_session.commit()
    resp = client.get("/api/v1/team/investigation-followups/other-team")
    assert resp.status_code == 404
