"""finalize_running_runs_for_thread and mark_stale_runs_as_timeout cutoff."""

from datetime import datetime, timedelta, timezone

import pytest

fastapi = pytest.importorskip("fastapi")
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


def test_finalize_marks_all_running_on_thread(db_session):
    repository.create_agent_run(
        db_session, run_id="a", org_id="local", team_node_id="default",
        correlation_id="t1", trigger_source="web_ui", agent_name="planner",
    )
    repository.create_agent_run(
        db_session, run_id="b", org_id="local", team_node_id="default",
        correlation_id="t1", trigger_source="web_ui", agent_name="planner",
    )
    repository.create_agent_run(
        db_session, run_id="c", org_id="local", team_node_id="default",
        correlation_id="t2", trigger_source="web_ui", agent_name="planner",
    )
    n = repository.finalize_running_runs_for_thread(
        db_session, correlation_id="t1", org_id="local", team_node_id="default"
    )
    assert n == 2
    assert repository.get_agent_run(db_session, run_id="a").status == "interrupted"
    assert repository.get_agent_run(db_session, run_id="b").status == "interrupted"
    assert repository.get_agent_run(db_session, run_id="c").status == "running"
    assert repository.get_agent_run(db_session, run_id="a").error_message == (
        repository.SUPERSEDED_ERROR_MESSAGE
    )


def test_finalize_zero_rows(db_session):
    n = repository.finalize_running_runs_for_thread(
        db_session, correlation_id="missing", org_id="local", team_node_id="default"
    )
    assert n == 0


def test_finalize_ignores_other_tenant(db_session):
    repository.create_agent_run(
        db_session, run_id="x", org_id="other", team_node_id="team",
        correlation_id="t1", trigger_source="web_ui", agent_name="planner",
    )
    n = repository.finalize_running_runs_for_thread(
        db_session, correlation_id="t1", org_id="local", team_node_id="default"
    )
    assert n == 0
    assert repository.get_agent_run(db_session, run_id="x").status == "running"


def test_mark_stale_runs_as_timeout_positive_cutoff(db_session):
    """Cron path: old running → timeout. Does not use max_age_seconds=0."""
    run = repository.create_agent_run(
        db_session, run_id="old", org_id="local", team_node_id="default",
        correlation_id="t-old", trigger_source="web_ui", agent_name="planner",
    )
    run.started_at = datetime.now(timezone.utc) - timedelta(seconds=120)
    db_session.flush()
    n = repository.mark_stale_runs_as_timeout(db_session, max_age_seconds=60)
    assert n == 1
    assert repository.get_agent_run(db_session, run_id="old").status == "timeout"


@pytest.fixture()
def internal_client(db_session):
    repository.create_agent_run(
        db_session,
        run_id="run-int-1",
        org_id="local",
        team_node_id="default",
        correlation_id="t1",
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


def test_internal_finalize_running_for_thread(internal_client):
    resp = internal_client.post(
        "/api/v1/internal/agent-runs/finalize-running-for-thread",
        headers={"X-Internal-Service": "sre-agent"},
        json={
            "correlation_id": "t1",
            "org_id": "local",
            "team_node_id": "default",
            "status": "interrupted",
            "error_message": "Superseded by new turn",
        },
    )
    assert resp.status_code == 200
    assert resp.json() == {"finalized_count": 1}


def test_internal_finalize_requires_header(internal_client):
    resp = internal_client.post(
        "/api/v1/internal/agent-runs/finalize-running-for-thread",
        json={"correlation_id": "t1", "org_id": "local", "team_node_id": "default"},
    )
    assert resp.status_code == 401
