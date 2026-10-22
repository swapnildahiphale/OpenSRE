"""Paginated investigation threads (grouped agent runs)."""

from datetime import datetime, timedelta, timezone

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.api.main import create_app
from src.core.security import hash_token
from src.db.models import AgentRun, NodeType, OrgNode, TeamToken
from src.db.session import get_db

UTC = timezone.utc
BASE_TIME = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)


@pytest.fixture()
def app_and_db(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    for table in (OrgNode, TeamToken, AgentRun):
        table.__table__.create(bind=engine)
    SessionLocal = sessionmaker(bind=engine)

    monkeypatch.setenv("TOKEN_PEPPER", "test-pepper")
    monkeypatch.setenv("DOTENV_AUTOLOAD", "0")

    import src.db.session as _db_session

    _db_session._SessionLocal = None
    monkeypatch.setattr(_db_session, "get_session_maker", lambda: SessionLocal)

    with SessionLocal() as s:
        s.add(
            OrgNode(
                org_id="org1",
                node_id="root",
                parent_id=None,
                node_type=NodeType.org,
                name="Root",
            )
        )
        s.add(
            OrgNode(
                org_id="org1",
                node_id="teamA",
                parent_id="root",
                node_type=NodeType.team,
                name="Team A",
            )
        )
        token_id = "tokid"
        token_secret = "toksecret"
        s.add(
            TeamToken(
                org_id="org1",
                team_node_id="teamA",
                token_id=token_id,
                token_hash=hash_token(token_secret, pepper="test-pepper"),
            )
        )

        # Thread A: three follow-up runs (same correlation id)
        for i in range(3):
            s.add(
                AgentRun(
                    id=f"run-a-{i}",
                    org_id="org1",
                    team_node_id="teamA",
                    correlation_id="thread-checkout",
                    trigger_source="web_ui",
                    agent_name="planner",
                    status="completed" if i < 2 else "running",
                    started_at=BASE_TIME + timedelta(hours=i),
                )
            )

        # Thread B: null correlation id — each run is its own investigation
        s.add(
            AgentRun(
                id="run-solo-1",
                org_id="org1",
                team_node_id="teamA",
                correlation_id=None,
                trigger_source="slack",
                agent_name="planner",
                status="completed",
                started_at=BASE_TIME + timedelta(days=1),
            )
        )
        s.add(
            AgentRun(
                id="run-solo-2",
                org_id="org1",
                team_node_id="teamA",
                correlation_id="",
                trigger_source="api",
                agent_name="planner",
                status="failed",
                started_at=BASE_TIME + timedelta(days=2),
            )
        )

        # Thread C: single run with correlation
        s.add(
            AgentRun(
                id="run-c-0",
                org_id="org1",
                team_node_id="teamA",
                correlation_id="thread-payments",
                trigger_source="teams",
                agent_name="planner",
                status="completed",
                started_at=BASE_TIME + timedelta(days=3),
            )
        )

        # Other team — must not appear in counts
        s.add(
            AgentRun(
                id="run-other",
                org_id="org1",
                team_node_id="teamB",
                correlation_id="thread-other",
                trigger_source="web_ui",
                agent_name="planner",
                status="completed",
                started_at=BASE_TIME,
            )
        )
        s.commit()

    def override_get_db():
        with SessionLocal() as s:
            try:
                yield s
                s.commit()
            except Exception:
                s.rollback()
                raise

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    return app, f"{token_id}.{token_secret}"


def test_investigations_total_and_page_size(app_and_db):
    app, token = app_and_db
    client = TestClient(app)
    resp = client.get(
        "/api/v1/team/investigations?page=1&page_size=2",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 4
    assert body["page"] == 1
    assert body["pageSize"] == 2
    assert len(body["items"]) == 2
    # Newest threads first: payments, solo-2, solo-1, checkout
    assert body["items"][0]["correlationId"] == "thread-payments"
    assert body["items"][1]["correlationId"] == "run-solo-2"


def test_investigations_thread_turn_count_and_latest_status(app_and_db):
    app, token = app_and_db
    client = TestClient(app)
    resp = client.get(
        "/api/v1/team/investigations?page=2&page_size=2",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 2
    checkout = next(
        i for i in body["items"] if i["correlationId"] == "thread-checkout"
    )
    assert checkout["turnCount"] == 3
    assert checkout["latestRun"]["id"] == "run-a-2"
    assert checkout["latestRun"]["status"] == "running"
    assert checkout["firstRun"]["id"] == "run-a-0"


def test_running_investigation_count(app_and_db):
    app, token = app_and_db
    client = TestClient(app)
    resp = client.get(
        "/api/v1/team/investigations",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["runningInvestigationCount"] == 1


def test_agent_runs_list_unchanged(app_and_db):
    app, token = app_and_db
    client = TestClient(app)
    resp = client.get(
        "/api/v1/team/agent-runs?limit=50",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    runs = resp.json()
    assert isinstance(runs, list)
    assert len(runs) == 6
