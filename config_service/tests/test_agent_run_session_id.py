"""sdk_session_id persists through create → complete on agent_runs."""

from datetime import datetime, timedelta

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


def test_set_sdk_session_id_on_running_row(db_session):
    repository.create_agent_run(
        db_session,
        run_id="run-sid-3",
        org_id="local",
        team_node_id="default",
        correlation_id="thread-inc",
        trigger_source="web_ui",
        agent_name="planner",
    )
    run = repository.set_agent_run_sdk_session_id(
        db_session, run_id="run-sid-3", sdk_session_id="sess-live"
    )
    assert run is not None
    assert run.sdk_session_id == "sess-live"
    assert run.status == "running"
    assert run.completed_at is None


def test_set_sdk_session_id_missing_run_returns_none(db_session):
    assert (
        repository.set_agent_run_sdk_session_id(
            db_session, run_id="nope", sdk_session_id="sess-x"
        )
        is None
    )


def test_set_sdk_session_id_blank_leaves_column(db_session):
    repository.create_agent_run(
        db_session,
        run_id="run-sid-blank",
        org_id="local",
        team_node_id="default",
        correlation_id="thread-blank",
        trigger_source="web_ui",
        agent_name="planner",
    )
    repository.set_agent_run_sdk_session_id(
        db_session, run_id="run-sid-blank", sdk_session_id="sess-keep"
    )
    run = repository.set_agent_run_sdk_session_id(
        db_session, run_id="run-sid-blank", sdk_session_id="   "
    )
    assert run.sdk_session_id == "sess-keep"
    assert run.status == "running"


def test_set_sdk_session_id_overwrites_different_value(db_session):
    repository.create_agent_run(
        db_session,
        run_id="run-sid-ow",
        org_id="local",
        team_node_id="default",
        correlation_id="thread-ow",
        trigger_source="web_ui",
        agent_name="planner",
    )
    repository.set_agent_run_sdk_session_id(
        db_session, run_id="run-sid-ow", sdk_session_id="sess-a"
    )
    run = repository.set_agent_run_sdk_session_id(
        db_session, run_id="run-sid-ow", sdk_session_id="sess-b"
    )
    assert run.sdk_session_id == "sess-b"


def test_complete_interrupted_preserves_sdk_session_id(db_session):
    repository.create_agent_run(
        db_session,
        run_id="run-sid-int",
        org_id="local",
        team_node_id="default",
        correlation_id="thread-int",
        trigger_source="web_ui",
        agent_name="planner",
    )
    repository.set_agent_run_sdk_session_id(
        db_session, run_id="run-sid-int", sdk_session_id="sess-keep"
    )
    run = repository.complete_agent_run(
        db_session, run_id="run-sid-int", status="interrupted"
    )
    assert run.status == "interrupted"
    assert run.sdk_session_id == "sess-keep"


def test_complete_without_sdk_session_id_does_not_wipe(db_session):
    repository.create_agent_run(
        db_session,
        run_id="run-sid-nowipe",
        org_id="local",
        team_node_id="default",
        correlation_id="thread-nowipe",
        trigger_source="web_ui",
        agent_name="planner",
    )
    repository.set_agent_run_sdk_session_id(
        db_session, run_id="run-sid-nowipe", sdk_session_id="sess-keep"
    )
    run = repository.complete_agent_run(
        db_session, run_id="run-sid-nowipe", status="completed"
    )
    assert run.sdk_session_id == "sess-keep"


def test_latest_sdk_session_id_prefers_newest_including_running(db_session):
    older = repository.create_agent_run(
        db_session,
        run_id="run-old",
        org_id="local",
        team_node_id="default",
        correlation_id="thread-latest",
        trigger_source="web_ui",
        agent_name="planner",
    )
    newer = repository.create_agent_run(
        db_session,
        run_id="run-new",
        org_id="local",
        team_node_id="default",
        correlation_id="thread-latest",
        trigger_source="web_ui",
        agent_name="planner",
    )
    older.started_at = datetime.utcnow() - timedelta(seconds=60)
    newer.started_at = datetime.utcnow()
    db_session.flush()
    repository.complete_agent_run(
        db_session, run_id="run-old", status="completed", sdk_session_id="sess-old"
    )
    repository.set_agent_run_sdk_session_id(
        db_session, run_id="run-new", sdk_session_id="sess-running"
    )
    sid = repository.get_latest_sdk_session_id(
        db_session,
        correlation_id="thread-latest",
        org_id="local",
        team_node_id="default",
    )
    assert sid == "sess-running"


def test_latest_sdk_session_id_skips_null_and_other_tenant(db_session):
    repository.create_agent_run(
        db_session,
        run_id="run-null",
        org_id="local",
        team_node_id="default",
        correlation_id="thread-mix",
        trigger_source="web_ui",
        agent_name="planner",
    )
    repository.create_agent_run(
        db_session,
        run_id="run-other",
        org_id="other",
        team_node_id="team",
        correlation_id="thread-mix",
        trigger_source="web_ui",
        agent_name="planner",
    )
    repository.set_agent_run_sdk_session_id(
        db_session, run_id="run-other", sdk_session_id="sess-other"
    )
    sid = repository.get_latest_sdk_session_id(
        db_session,
        correlation_id="thread-mix",
        org_id="local",
        team_node_id="default",
    )
    assert sid is None


def test_latest_sdk_session_id_empty_thread(db_session):
    assert (
        repository.get_latest_sdk_session_id(
            db_session,
            correlation_id="missing",
            org_id="local",
            team_node_id="default",
        )
        is None
    )
