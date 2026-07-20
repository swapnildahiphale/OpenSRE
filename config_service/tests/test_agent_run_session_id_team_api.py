"""sdkSessionId is exposed on the team-facing agent-run endpoints."""

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


@pytest.fixture()
def app_and_db(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # Only create the tables we need; the full Base.metadata.create_all fails
    # on SQLite because some models use JSONB/EncryptedJSONB.
    for table in (OrgNode, TeamToken, AgentRun):
        table.__table__.create(bind=engine)
    SessionLocal = sessionmaker(bind=engine)

    monkeypatch.setenv("TOKEN_PEPPER", "test-pepper")
    monkeypatch.setenv("DOTENV_AUTOLOAD", "0")

    # Patch get_session_maker so auth.py (which calls get_db() directly, not
    # via dependency injection) also uses our in-memory engine.
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

        # A run with an sdk_session_id set
        s.add(
            AgentRun(
                id="run-team-1",
                org_id="org1",
                team_node_id="teamA",
                correlation_id="corr-1",
                trigger_source="web_ui",
                agent_name="planner",
                status="completed",
                sdk_session_id="sess-abc123",
            )
        )
        # A run without an sdk_session_id
        s.add(
            AgentRun(
                id="run-team-2",
                org_id="org1",
                team_node_id="teamA",
                correlation_id="corr-2",
                trigger_source="web_ui",
                agent_name="planner",
                status="running",
                sdk_session_id=None,
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


def test_list_agent_runs_includes_sdk_session_id(app_and_db):
    app, token = app_and_db
    client = TestClient(app)
    resp = client.get(
        "/api/v1/team/agent-runs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    runs = resp.json()
    assert isinstance(runs, list)
    assert len(runs) == 2

    by_id = {r["id"]: r for r in runs}
    assert by_id["run-team-1"]["sdkSessionId"] == "sess-abc123"
    assert by_id["run-team-2"]["sdkSessionId"] is None


def test_get_agent_run_includes_sdk_session_id(app_and_db):
    app, token = app_and_db
    client = TestClient(app)
    resp = client.get(
        "/api/v1/team/agent-runs/run-team-1",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["sdkSessionId"] == "sess-abc123"


def test_get_agent_run_null_sdk_session_id(app_and_db):
    app, token = app_and_db
    client = TestClient(app)
    resp = client.get(
        "/api/v1/team/agent-runs/run-team-2",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["sdkSessionId"] is None
