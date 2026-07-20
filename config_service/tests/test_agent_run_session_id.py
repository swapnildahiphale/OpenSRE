"""sdk_session_id persists through create → complete on agent_runs."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from src.db import repository
from src.db.models import AgentRun


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # Only create the agent_runs table to avoid EncryptedJSONB incompatibility
    # with SQLite on other tables (e.g. integrations).
    AgentRun.__table__.create(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    with SessionLocal() as s:
        yield s


def test_complete_agent_run_persists_sdk_session_id(db_session):
    repository.create_agent_run(
        db_session,
        run_id="run-sid-1",
        org_id="local",
        team_node_id="default",
        correlation_id="thread-abc",
        trigger_source="web_ui",
        agent_name="planner",
    )
    run = repository.complete_agent_run(
        db_session,
        run_id="run-sid-1",
        status="completed",
        sdk_session_id="sess-xyz",
    )
    assert run is not None
    assert run.sdk_session_id == "sess-xyz"


def test_complete_agent_run_without_session_id_leaves_none(db_session):
    repository.create_agent_run(
        db_session,
        run_id="run-sid-2",
        org_id="local",
        team_node_id="default",
        correlation_id="thread-def",
        trigger_source="web_ui",
        agent_name="planner",
    )
    run = repository.complete_agent_run(
        db_session, run_id="run-sid-2", status="completed"
    )
    assert run is not None
    assert run.sdk_session_id is None
