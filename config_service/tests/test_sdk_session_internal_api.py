"""Internal PUT sdk-session and GET latest-sdk-session."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.api.routes.internal import router as internal_router
from src.db import repository
from src.db.models import AgentRun
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


@pytest.fixture()
def internal_client(db_session):
    repository.create_agent_run(
        db_session,
        run_id="run-http-1",
        org_id="local",
        team_node_id="default",
        correlation_id="t-http",
        trigger_source="web_ui",
        agent_name="planner",
    )
    db_session.commit()

    app = FastAPI()
    app.include_router(internal_router)

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def test_put_sdk_session_on_running_run(internal_client, db_session):
    resp = internal_client.put(
        "/api/v1/internal/agent-runs/run-http-1/sdk-session",
        headers={"X-Internal-Service": "sre-agent"},
        json={"sdk_session_id": "sess-http"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"success": True, "sdk_session_id": "sess-http"}
    run = repository.get_agent_run(db_session, run_id="run-http-1")
    assert run.status == "running"
    assert run.completed_at is None
    assert run.sdk_session_id == "sess-http"


def test_put_sdk_session_unknown_run_404(internal_client):
    resp = internal_client.put(
        "/api/v1/internal/agent-runs/missing/sdk-session",
        headers={"X-Internal-Service": "sre-agent"},
        json={"sdk_session_id": "sess-x"},
    )
    assert resp.status_code == 404


def test_put_sdk_session_blank_422(internal_client):
    resp = internal_client.put(
        "/api/v1/internal/agent-runs/run-http-1/sdk-session",
        headers={"X-Internal-Service": "sre-agent"},
        json={"sdk_session_id": ""},
    )
    assert resp.status_code == 422


def test_put_sdk_session_requires_header(internal_client):
    resp = internal_client.put(
        "/api/v1/internal/agent-runs/run-http-1/sdk-session",
        json={"sdk_session_id": "sess-x"},
    )
    assert resp.status_code == 401


def test_get_latest_sdk_session(internal_client, db_session):
    repository.set_agent_run_sdk_session_id(
        db_session, run_id="run-http-1", sdk_session_id="sess-http"
    )
    db_session.commit()
    resp = internal_client.get(
        "/api/v1/internal/agent-runs/latest-sdk-session",
        headers={"X-Internal-Service": "sre-agent"},
        params={
            "correlation_id": "t-http",
            "org_id": "local",
            "team_node_id": "default",
        },
    )
    assert resp.status_code == 200
    assert resp.json() == {"sdk_session_id": "sess-http"}


def test_get_latest_sdk_session_null_when_unset(internal_client):
    resp = internal_client.get(
        "/api/v1/internal/agent-runs/latest-sdk-session",
        headers={"X-Internal-Service": "sre-agent"},
        params={
            "correlation_id": "t-http",
            "org_id": "local",
            "team_node_id": "default",
        },
    )
    assert resp.status_code == 200
    assert resp.json() == {"sdk_session_id": None}


def test_get_latest_sdk_session_is_not_captured_as_run_id(internal_client):
    """Static path must win over GET /agent-runs/{run_id}."""
    resp = internal_client.get(
        "/api/v1/internal/agent-runs/latest-sdk-session",
        headers={"X-Internal-Service": "sre-agent"},
        params={
            "correlation_id": "t-http",
            "org_id": "local",
            "team_node_id": "default",
        },
    )
    assert resp.status_code == 200
    assert "sdk_session_id" in resp.json()
