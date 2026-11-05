"""investigation_followups round-trip — delivery-only nudge row."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from src.db.investigation_followups import InvestigationFollowup


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


def test_insert_round_trip_defaults(db_session):
    row = InvestigationFollowup(
        correlation_id="teams-19:abc;messageid=123",
        org_id="local",
        team_node_id="default",
        entry_channel="teams",
    )
    db_session.add(row)
    db_session.commit()

    loaded = db_session.get(InvestigationFollowup, "teams-19:abc;messageid=123")
    assert loaded is not None
    assert loaded.org_id == "local"
    assert loaded.team_node_id == "default"
    assert loaded.entry_channel == "teams"
    assert loaded.nudge_count == 0
    assert loaded.nudge_due_at is None
    assert loaded.stopped_at is None
    assert loaded.trigger_actor_name is None
    assert loaded.trigger_actor_teams_id is None
    assert loaded.conversation_ref is None
    assert loaded.last_nudge_text is None
    assert loaded.created_at is not None
    assert loaded.updated_at is not None


def test_conversation_ref_json_round_trip(db_session):
    ref = {
        "conversation_id": "19:abc",
        "service_url": "https://smba.trafficmanager.net/in/",
        "channel_id": "msteams",
        "tenant_id": "tenant-1",
    }
    db_session.add(
        InvestigationFollowup(
            correlation_id="thread-1",
            org_id="org",
            team_node_id="team",
            entry_channel="web",
            conversation_ref=ref,
            nudge_due_at=datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc),
            last_nudge_text="Has this been fixed yet?",
        )
    )
    db_session.commit()

    loaded = db_session.get(InvestigationFollowup, "thread-1")
    assert loaded.conversation_ref == ref
    assert loaded.last_nudge_text == "Has this been fixed yet?"
    assert loaded.nudge_due_at is not None


def test_table_has_due_and_team_indexes():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    InvestigationFollowup.__table__.create(bind=engine)
    names = {idx["name"] for idx in inspect(engine).get_indexes("investigation_followups")}
    assert "ix_investigation_followups_due" in names
    assert "ix_investigation_followups_team" in names
