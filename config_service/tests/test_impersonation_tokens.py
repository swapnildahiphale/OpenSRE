import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from src.api.main import create_app
from src.core.security import hash_token
from src.db.base import Base
from src.db.models import NodeConfig, NodeType, OrgNode, TeamToken


@pytest.fixture()
def app_admin_and_team(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)

    monkeypatch.setenv("ADMIN_TOKEN", "admin-secret")
    monkeypatch.setenv("ADMIN_AUTH_MODE", "token")
    monkeypatch.setenv("TEAM_AUTH_MODE", "token")
    monkeypatch.setenv("TOKEN_PEPPER", "test-pepper")
    monkeypatch.setenv("IMPERSONATION_JWT_SECRET", "impersonation-secret")
    monkeypatch.setenv("IMPERSONATION_TOKEN_TTL_SECONDS", "600")

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
        s.add(
            NodeConfig(
                org_id="org1",
                node_id="root",
                config_json={"knowledge_source": {"grafana": ["org"]}},
                version=1,
            )
        )
        s.add(
            NodeConfig(
                org_id="org1",
                node_id="teamA",
                config_json={"knowledge_source": {"confluence": ["team"]}},
                version=1,
            )
        )
        s.add(
            TeamToken(
                org_id="org1",
                team_node_id="teamA",
                token_id="tokid",
                token_hash=hash_token("toksecret", pepper="test-pepper"),
            )
        )
        s.commit()

    from src.api.routes import admin as admin_routes
    from src.api.routes import auth_me, config_me

    def override_get_db():
        with SessionLocal() as s:
            try:
                yield s
                s.commit()
            except Exception:
                s.rollback()
                raise

    app = create_app()
    app.dependency_overrides[admin_routes.get_db] = override_get_db
    app.dependency_overrides[config_me.get_db] = override_get_db
    app.dependency_overrides[auth_me.get_db] = override_get_db
    return app


def test_impersonation_token_can_read_team_config(app_admin_and_team):
    client = TestClient(app_admin_and_team)

    r = client.post(
        "/api/v1/admin/orgs/org1/teams/teamA/impersonation-token",
        headers={"Authorization": "Bearer admin-secret"},
    )
    assert r.status_code == 200
    tok = r.json()["token"]
    assert tok.count(".") == 2

    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tok}"})
    assert me.status_code == 200
    body = me.json()
    assert body["role"] == "team"
    assert body["auth_kind"] == "impersonation"
    assert body["org_id"] == "org1"
    assert body["team_node_id"] == "teamA"
    assert body["can_write"] is False

    eff = client.get(
        "/api/v1/config/me/effective", headers={"Authorization": f"Bearer {tok}"}
    )
    assert eff.status_code == 200
    cfg = eff.json()
    assert cfg["knowledge_source"]["grafana"] == ["org"]
    assert cfg["knowledge_source"]["confluence"] == ["team"]


def test_impersonation_token_cannot_write(app_admin_and_team):
    client = TestClient(app_admin_and_team)
    r = client.post(
        "/api/v1/admin/orgs/org1/teams/teamA/impersonation-token",
        headers={"Authorization": "Bearer admin-secret"},
    )
    tok = r.json()["token"]

    put = client.put(
        "/api/v1/config/me",
        headers={"Authorization": f"Bearer {tok}"},
        json={"knowledge_source": {"google": ["drive:folder/demo"]}},
    )
    assert put.status_code == 403


def test_impersonation_token_db_allowlist_optional(app_admin_and_team, monkeypatch):
    # Enable DB-backed tracking at mint-time + require allowlist on verify.
    monkeypatch.setenv("IMPERSONATION_JTI_DB_LOGGING", "1")
    monkeypatch.setenv("IMPERSONATION_JTI_DB_REQUIRE", "1")

    client = TestClient(app_admin_and_team)
    r = client.post(
        "/api/v1/admin/orgs/org1/teams/teamA/impersonation-token",
        headers={"Authorization": "Bearer admin-secret"},
    )
    assert r.status_code == 200
    tok = r.json()["token"]

    eff = client.get(
        "/api/v1/config/me/effective", headers={"Authorization": f"Bearer {tok}"}
    )
    assert eff.status_code == 200


def test_impersonation_token_db_allowlist_blocks_untracked_tokens(
    app_admin_and_team, monkeypatch
):
    # Require allowlist, but do not record JTIs at mint-time.
    monkeypatch.setenv("IMPERSONATION_JTI_DB_LOGGING", "0")
    monkeypatch.setenv("IMPERSONATION_JTI_DB_REQUIRE", "1")

    client = TestClient(app_admin_and_team)
    r = client.post(
        "/api/v1/admin/orgs/org1/teams/teamA/impersonation-token",
        headers={"Authorization": "Bearer admin-secret"},
    )
    assert r.status_code == 200
    tok = r.json()["token"]

    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tok}"})
    assert me.status_code == 401
