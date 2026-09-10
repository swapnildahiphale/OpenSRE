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
from src.api.routes.auth_me import sso_persona_from_token
from src.core.security import hash_token
from src.db.models import NodeType, OrgNode, TeamToken


def test_sso_persona_from_sso_label_with_name():
    email, name, subject = sso_persona_from_token("sso:jane@example.com", "Jane Doe")
    assert email == "jane@example.com"
    assert name == "Jane Doe"
    assert subject == "jane@example.com"


def test_sso_persona_from_sso_label_without_name():
    email, name, subject = sso_persona_from_token("sso:jane@example.com", None)
    assert email == "jane@example.com"
    assert name is None
    assert subject == "jane@example.com"


def test_sso_persona_ignores_non_sso_label():
    assert sso_persona_from_token("local-dev", "ShouldIgnore") == (None, None, None)
    assert sso_persona_from_token("jane@example.com", None) == (None, None, None)
    assert sso_persona_from_token("sso:not-an-email", "Jane") == (None, None, None)
    assert sso_persona_from_token(None, "Jane") == (None, None, None)


@pytest.fixture()
def app_db_team(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # Only create tables needed for token auth; full create_all fails on SQLite JSONB.
    for table in (OrgNode, TeamToken):
        table.__table__.create(bind=engine)
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
        s.add(
            TeamToken(
                org_id="org1",
                team_node_id="teamA",
                token_id="tokid",
                token_hash=hash_token("toksecret", pepper="test-pepper"),
            )
        )
        s.commit()

    from src.api.routes import auth_me

    def override_get_db():
        with SessionLocal() as s:
            try:
                yield s
                s.commit()
            except Exception:
                s.rollback()
                raise

    app = create_app()
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
    assert body.get("name") is None
    assert body.get("email") is None
    assert body.get("subject") is None


def test_auth_me_team_token_has_no_persona(app_db_team):
    client = TestClient(app_db_team)
    r = client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer tokid.toksecret"}
    )
    body = r.json()
    assert body.get("name") is None
    assert body.get("email") is None
    assert body.get("subject") is None


@pytest.fixture()
def app_db_sso(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # Only create tables needed for token auth; full create_all fails on SQLite JSONB.
    for table in (OrgNode, TeamToken):
        table.__table__.create(bind=engine)
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
                node_id="default",
                parent_id="root",
                node_type=NodeType.team,
                name="Default",
            )
        )
        s.add(
            TeamToken(
                org_id="org1",
                team_node_id="default",
                token_id="ssotok",
                token_hash=hash_token("ssosecret", pepper="test-pepper"),
                label="sso:jane@example.com",
                display_name="Jane Doe",
            )
        )
        s.commit()

    from src.api.routes import auth_me

    def override_get_db():
        with SessionLocal() as s:
            try:
                yield s
                s.commit()
            except Exception:
                s.rollback()
                raise

    app = create_app()
    app.dependency_overrides[auth_me.get_db] = override_get_db
    return app


def test_auth_me_sso_token_returns_name_and_email(app_db_sso):
    client = TestClient(app_db_sso)
    r = client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer ssotok.ssosecret"}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "team"
    assert body["email"] == "jane@example.com"
    assert body["name"] == "Jane Doe"
    assert body["subject"] == "jane@example.com"


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
