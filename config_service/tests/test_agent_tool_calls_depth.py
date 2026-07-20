"""agent_id/depth persist through bulk_create_tool_calls (nested-agent attribution)."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from src.db import repository
from src.db.models import AgentToolCall


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # Only create the agent_tool_calls table to avoid EncryptedJSONB
    # incompatibility with SQLite on other tables (e.g. integrations).
    AgentToolCall.__table__.create(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    with SessionLocal() as s:
        yield s


def test_bulk_create_tool_calls_persists_agent_id_and_depth(db_session):
    count = repository.bulk_create_tool_calls(
        db_session,
        run_id="run-1",
        tool_calls=[
            {
                "id": "t1",
                "tool_name": "Bash",
                "agent_name": "investigation",
                "parent_agent": "planner",
                "agent_id": "agent-A",
                "depth": 1,
                "tool_input": {},
                "tool_output": "ok",
                "sequence_number": 0,
            }
        ],
    )
    db_session.commit()
    assert count == 1
    rows = repository.get_tool_calls_for_run(db_session, run_id="run-1")
    assert rows[0].agent_id == "agent-A"
    assert rows[0].depth == 1


def test_bulk_create_tool_calls_defaults_depth_zero_without_agent_id(db_session):
    """Older callers that don't send the new fields still persist cleanly."""
    repository.bulk_create_tool_calls(
        db_session,
        run_id="run-2",
        tool_calls=[
            {
                "id": "t2",
                "tool_name": "Bash",
                "agent_name": "planner",
                "tool_input": {},
                "tool_output": "ok",
                "sequence_number": 0,
            }
        ],
    )
    db_session.commit()
    rows = repository.get_tool_calls_for_run(db_session, run_id="run-2")
    assert rows[0].agent_id is None
    assert rows[0].depth == 0


def test_bulk_create_tool_calls_persists_parent_agent_id(db_session):
    repository.bulk_create_tool_calls(
        db_session,
        run_id="run-3",
        tool_calls=[
            {
                "id": "t3",
                "tool_name": "Bash",
                "agent_name": "general-purpose",
                "parent_agent": "investigation",
                "agent_id": "task-2",
                "parent_agent_id": "task-1",
                "depth": 2,
                "tool_input": {},
                "tool_output": "ok",
                "sequence_number": 0,
            }
        ],
    )
    db_session.commit()
    rows = repository.get_tool_calls_for_run(db_session, run_id="run-3")
    assert rows[0].agent_id == "task-2"
    assert rows[0].parent_agent_id == "task-1"
