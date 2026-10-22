"""Team /stats counts distinct investigation threads, not raw run rows."""

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

        # Thread A: three follow-up runs sharing one correlation id
        for i in range(3):
            s.add(
                AgentRun(
                    id=f"run-thread-a-{i}",
                    org_id="org1",
                    team_node_id="teamA",
                    correlation_id="corr-thread-a",
                    trigger_source="web_ui",
                    agent_name="planner",
                    status="completed",
                )
            )

        # Thread B: single run with null correlation id (thread key = run id)
        s.add(
            AgentRun(
                id="run-standalone",
                org_id="org1",
                team_node_id="teamA",
                correlation_id=None,
                trigger_source="web_ui",
                agent_name="planner",
                status="completed",
            )
        )

        # Another null-correlation run is its own thread
        s.add(
            AgentRun(
                id="run-standalone-2",
                org_id="org1",
                team_node_id="teamA",
                correlation_id=None,
                trigger_source="web_ui",
                agent_name="planner",
                status="failed",
            )
        )

        # Thread C: two runs
        for i in range(2):
            s.add(
                AgentRun(
                    id=f"run-thread-c-{i}",
                    org_id="org1",
                    team_node_id="teamA",
                    correlation_id="corr-thread-c",
                    trigger_source="api",
                    agent_name="planner",
                    status="completed",
                )
            )

        # Other team — must not affect counts
        s.add(
            AgentRun(
                id="run-other-team",
                org_id="org1",
                team_node_id="teamB",
                correlation_id="corr-other",
                trigger_source="web_ui",
                agent_name="planner",
                status="completed",
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


def test_team_stats_distinct_investigation_count(app_and_db):
    app, token = app_and_db
    client = TestClient(app)
    resp = client.get(
        "/api/v1/team/stats",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()

    # 3 + 1 + 1 + 2 = 7 runs for teamA; 4 distinct threads
    assert body["totalRuns"] == 7
    assert body["totalInvestigations"] == 4
