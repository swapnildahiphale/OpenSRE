"""abandon_agent_run marks one tenant running row interrupted."""

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.api.main import create_app
from src.core.security import hash_token
from src.db import repository
from src.db.models import AgentRun, NodeType, OrgNode, TeamToken
from src.db.session import get_db


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    AgentRun.__table__.create(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    with SessionLocal() as s:
        yield s


def _running(session, run_id, org_id="local", team_node_id="default", corr="thread-a"):
    return repository.create_agent_run(
        session,
        run_id=run_id,
        org_id=org_id,
        team_node_id=team_node_id,
        correlation_id=corr,
        trigger_source="web_ui",
        agent_name="planner",
    )


def test_abandon_running_sets_interrupted(db_session):
    _running(db_session, "run-1")
    run = repository.abandon_agent_run(
        db_session, run_id="run-1", org_id="local", team_node_id="default"
    )
    assert run is not None
    assert run.status == "interrupted"
    assert run.error_message == repository.ABANDON_ERROR_MESSAGE
    assert run.completed_at is not None


def test_abandon_wrong_tenant_returns_none(db_session):
    _running(db_session, "run-2", org_id="org-b", team_node_id="team-b")
    run = repository.abandon_agent_run(
        db_session, run_id="run-2", org_id="local", team_node_id="default"
    )
    assert run is None
    still = repository.get_agent_run(db_session, run_id="run-2")
    assert still.status == "running"


def test_abandon_missing_returns_none(db_session):
    assert repository.abandon_agent_run(
        db_session, run_id="nope", org_id="local", team_node_id="default"
    ) is None


def test_abandon_not_running_leaves_status(db_session):
    _running(db_session, "run-3")
    repository.complete_agent_run(db_session, run_id="run-3", status="completed")
    run = repository.abandon_agent_run(
        db_session, run_id="run-3", org_id="local", team_node_id="default"
    )
    assert run is not None
    assert run.status == "completed"


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

        s.add(
            AgentRun(
                id="run-ab-1",
                org_id="org1",
                team_node_id="teamA",
                correlation_id="corr-1",
                trigger_source="web_ui",
                agent_name="planner",
                status="running",
            )
        )
        s.add(
            AgentRun(
                id="run-ab-done",
                org_id="org1",
                team_node_id="teamA",
                correlation_id="corr-2",
                trigger_source="web_ui",
                agent_name="planner",
                status="completed",
            )
        )
        s.add(
            AgentRun(
                id="run-ab-other",
                org_id="org-other",
                team_node_id="team-other",
                correlation_id="corr-3",
                trigger_source="web_ui",
                agent_name="planner",
                status="running",
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


def test_team_abandon_running_200(app_and_db):
    app, token = app_and_db
    client = TestClient(app)
    resp = client.post(
        "/api/v1/team/agent-runs/run-ab-1/abandon",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == "run-ab-1"
    assert body["status"] == "interrupted"
    assert body["errorMessage"] == repository.ABANDON_ERROR_MESSAGE
    assert body["completedAt"] is not None


def test_team_abandon_not_running_409(app_and_db):
    app, token = app_and_db
    client = TestClient(app)
    resp = client.post(
        "/api/v1/team/agent-runs/run-ab-done/abandon",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"] == "Run is not in running state"


def test_team_abandon_wrong_tenant_404(app_and_db):
    app, token = app_and_db
    client = TestClient(app)
    resp = client.post(
        "/api/v1/team/agent-runs/run-ab-other/abandon",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


def test_team_abandon_unauthorized_401(app_and_db):
    app, _token = app_and_db
    client = TestClient(app)
    resp = client.post("/api/v1/team/agent-runs/run-ab-1/abandon")
    assert resp.status_code == 401
