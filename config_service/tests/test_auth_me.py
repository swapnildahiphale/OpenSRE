import time

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

jwt = pytest.importorskip("jwt")
cryptography = pytest.importorskip("cryptography")
from cryptography.hazmat.primitives.asymmetric import rsa
from src.api.main import create_app
from src.core.security import hash_token
from src.db.base import Base
from src.db.models import NodeConfig, NodeType, OrgNode, TeamToken


@pytest.fixture()
def app_db_team(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)

    monkeypatch.setenv("TOKEN_PEPPER", "test-pepper")
    monkeypatch.setenv("TEAM_AUTH_MODE", "token")

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
        s.add(NodeConfig(org_id="org1", node_id="root", config_json={}, version=1))
        s.add(NodeConfig(org_id="org1", node_id="teamA", config_json={}, version=1))
        s.add(
            TeamToken(
                org_id="org1",
                team_node_id="teamA",
                token_id="tokid",
                token_hash=hash_token("toksecret", pepper="test-pepper"),
            )
        )
        s.commit()

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
    app.dependency_overrides[config_me.get_db] = override_get_db
    app.dependency_overrides[auth_me.get_db] = override_get_db
    return app


def test_auth_me_team_token(app_db_team):
    client = TestClient(app_db_team)
    r = client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer tokid.toksecret"}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "team"
    assert body["auth_kind"] == "team_token"
    assert body["org_id"] == "org1"
    assert body["team_node_id"] == "teamA"
    assert body["can_write"] is True


def test_auth_me_admin_token(monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "admin-secret")
    monkeypatch.setenv("ADMIN_AUTH_MODE", "token")
    app = create_app()
    client = TestClient(app)

    r = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer admin-secret"})
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "admin"
    assert body["auth_kind"] == "admin_token"
    assert body["can_write"] is True


def test_auth_me_team_oidc(monkeypatch):
    # Team OIDC mode
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pub = key.public_key()
    jwk = jwt.algorithms.RSAAlgorithm.to_jwk(pub)
    jwks = {"keys": [dict(**__import__("json").loads(jwk), kid="kid1")]}

    monkeypatch.setenv("TEAM_AUTH_MODE", "oidc")
    monkeypatch.setenv("OIDC_ENABLED", "1")
    monkeypatch.setenv("OIDC_ISSUER", "https://issuer.example")
    monkeypatch.setenv("OIDC_AUDIENCE", "opensre-config-service")
    monkeypatch.setenv("OIDC_JWKS_JSON", __import__("json").dumps(jwks))
    monkeypatch.setenv("OIDC_ORG_ID_CLAIM", "org_id")
    monkeypatch.setenv("OIDC_TEAM_NODE_ID_CLAIM", "team_node_id")
    monkeypatch.setenv("TEAM_OIDC_WRITE_ENABLED", "0")

    token = jwt.encode(
        {
            "sub": "user1",
            "iss": "https://issuer.example",
            "aud": "opensre-config-service",
            "org_id": "org1",
            "team_node_id": "teamA",
            "exp": int(time.time()) + 3600,
        },
        key,
        algorithm="RS256",
        headers={"kid": "kid1"},
    )

    app = create_app()
    client = TestClient(app)
    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "team"
    assert body["auth_kind"] == "oidc"
    assert body["org_id"] == "org1"
    assert body["team_node_id"] == "teamA"
    assert body["can_write"] is False
