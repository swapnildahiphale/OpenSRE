"""Tests for GitHub App install callback state validation."""

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.types import JSON

from src.api.main import create_app
from src.core.github_install_state import clear_install_state_store, mint_install_state
from src.db.models import GitHubInstallation, NodeType, OrgNode
from src.db.session import get_db


def _create_sqlite_tables(engine, models):
    """Create only the tables needed for GitHub route tests on SQLite."""
    if engine.dialect.name == "sqlite":
        for model in models:
            for column in model.__table__.columns:
                if isinstance(column.type, JSONB):
                    column.type = JSON()
    for model in models:
        model.__table__.create(bind=engine)


def _sample_installation_payload(installation_id: int = 12345) -> dict:
    return {
        "id": installation_id,
        "app_id": 999,
        "account": {
            "id": 42,
            "login": "example-org",
            "type": "Organization",
            "avatar_url": "https://example.com/avatar.png",
        },
        "permissions": {"contents": "read"},
        "repository_selection": "all",
    }


@pytest.fixture()
def app_github(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    _create_sqlite_tables(engine, (OrgNode, GitHubInstallation))
    SessionLocal = sessionmaker(bind=engine)

    monkeypatch.setenv("TOKEN_PEPPER", "test-pepper")
    monkeypatch.setenv("ADMIN_TOKEN", "admin-secret")
    monkeypatch.setenv("GITHUB_APP_ID", "999")
    monkeypatch.setenv("GITHUB_APP_NAME", "opensre-test")

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
    clear_install_state_store()
    app.state.test_session_local = SessionLocal
    yield app
    clear_install_state_store()


@pytest.fixture()
def client(app_github):
    return TestClient(app_github)


@pytest.fixture()
def admin_headers():
    return {"Authorization": "Bearer admin-secret"}


def test_install_start_requires_admin(client):
    r = client.get("/github/install/start")
    assert r.status_code in (401, 503)


def test_install_start_mints_state(client, admin_headers):
    r = client.get("/github/install/start", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["state"]
    assert "state=" in body["install_url"]
    assert "opensre-test" in body["install_url"]


def test_callback_missing_state_fails(client, monkeypatch):
    async def fake_fetch(installation_id, config):
        return _sample_installation_payload(installation_id)

    monkeypatch.setattr(
        "src.api.routes.github._fetch_installation_details",
        fake_fetch,
    )

    r = client.get("/github/callback", params={"installation_id": 12345})
    assert r.status_code == 400
    assert "state" in r.json()["detail"].lower()


def test_callback_invalid_state_fails(client, monkeypatch):
    async def fake_fetch(installation_id, config):
        return _sample_installation_payload(installation_id)

    monkeypatch.setattr(
        "src.api.routes.github._fetch_installation_details",
        fake_fetch,
    )

    r = client.get(
        "/github/callback",
        params={"installation_id": 12345, "state": "not-a-real-state"},
    )
    assert r.status_code == 403
    assert "invalid" in r.json()["detail"].lower()


def test_callback_valid_state_succeeds(client, monkeypatch, admin_headers):
    install = client.get("/github/install/start", headers=admin_headers)
    state = install.json()["state"]

    async def fake_fetch(installation_id, config):
        return _sample_installation_payload(installation_id)

    monkeypatch.setattr(
        "src.api.routes.github._fetch_installation_details",
        fake_fetch,
    )

    r = client.get(
        "/github/callback",
        params={
            "installation_id": 12345,
            "setup_action": "install",
            "state": state,
        },
        follow_redirects=False,
    )
    assert r.status_code == 302
    assert "installation_id=12345" in r.headers["location"]
    assert "example-org" in r.headers["location"]

    SessionLocal = client.app.state.test_session_local
    with SessionLocal() as session:
        row = (
            session.query(GitHubInstallation)
            .filter(GitHubInstallation.installation_id == 12345)
            .first()
        )
        assert row is not None
        assert row.account_login == "example-org"


def test_callback_state_is_one_time_use(client, monkeypatch, admin_headers):
    install = client.get("/github/install/start", headers=admin_headers)
    state = install.json()["state"]

    async def fake_fetch(installation_id, config):
        return _sample_installation_payload(installation_id)

    monkeypatch.setattr(
        "src.api.routes.github._fetch_installation_details",
        fake_fetch,
    )

    first = client.get(
        "/github/callback",
        params={"installation_id": 12345, "state": state},
        follow_redirects=False,
    )
    assert first.status_code == 302

    second = client.get(
        "/github/callback",
        params={"installation_id": 12345, "state": state},
    )
    assert second.status_code == 403


def test_get_installation_requires_admin(client, app_github):
    SessionLocal = app_github.state.test_session_local
    with SessionLocal() as session:
        session.add(
            GitHubInstallation(
                id="inst-1",
                installation_id=777,
                app_id=999,
                account_id=42,
                account_login="example-org",
                account_type="Organization",
                status="active",
            )
        )
        session.commit()

    r = client.get("/github/installations/777")
    assert r.status_code in (401, 503)


def test_get_installation_with_admin(client, app_github, admin_headers):
    SessionLocal = app_github.state.test_session_local
    with SessionLocal() as session:
        session.add(
            GitHubInstallation(
                id="inst-1",
                installation_id=777,
                app_id=999,
                account_id=42,
                account_login="example-org",
                account_type="Organization",
                status="active",
            )
        )
        session.commit()

    r = client.get("/github/installations/777", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["installation_id"] == 777
    assert body["account_login"] == "example-org"


def test_mint_install_state_helper():
    clear_install_state_store()
    state = mint_install_state(created_by="test")
    assert state
    clear_install_state_store()
