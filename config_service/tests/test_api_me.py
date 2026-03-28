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
def app_and_db(monkeypatch):
    # sqlite in-memory for tests
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)

    # required for token hashing
    monkeypatch.setenv("TOKEN_PEPPER", "test-pepper")

    # Seed org graph + configs
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

        # create token row
        token_id = "tokid"
        token_secret = "toksecret"
        s.add(
            TeamToken(
                org_id="org1",
                team_node_id="teamA",
                token_id=token_id,
                token_hash=hash_token(token_secret, pepper="test-pepper"),
            )
        )
        s.commit()

    # Override the DB dependency to use this sessionmaker
    from src.api.routes import config_me

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
    return app, f"{token_id}.{token_secret}"


def test_me_effective(app_and_db):
    app, token = app_and_db
    client = TestClient(app)
    resp = client.get(
        "/api/v1/config/me/effective", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    body = resp.json()
    # team overrides wins for confluence; grafana inherited from org remains
    assert body["knowledge_source"]["grafana"] == ["org"]
    assert body["knowledge_source"]["confluence"] == ["team"]


def test_me_raw(app_and_db):
    app, token = app_and_db
    client = TestClient(app)
    resp = client.get(
        "/api/v1/config/me/raw", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert [n["node_id"] for n in body["lineage"]] == ["root", "teamA"]
    assert body["configs"]["root"]["knowledge_source"]["grafana"] == ["org"]


def test_me_audit_after_put(app_and_db):
    app, token = app_and_db
    client = TestClient(app)

    # initial history may be empty because fixtures insert NodeConfig directly
    r0 = client.get(
        "/api/v1/config/me/audit", headers={"Authorization": f"Bearer {token}"}
    )
    assert r0.status_code == 200

    # write an override to generate an audit row
    p = client.put(
        "/api/v1/config/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"knowledge_source": {"google": ["drive:folder/demo"]}},
    )
    assert p.status_code == 200

    r1 = client.get(
        "/api/v1/config/me/audit?limit=10&include_full=true",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r1.status_code == 200
    rows = r1.json()
    assert isinstance(rows, list)
    assert len(rows) >= 1
    latest = rows[0]
    assert latest["node_id"] == "teamA"
    assert "diff" in latest
    assert "full_config" in latest


def test_put_me_rejects_team_name(app_and_db):
    app, token = app_and_db
    client = TestClient(app)
    resp = client.put(
        "/api/v1/config/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"team_name": "nope"},
    )
    assert resp.status_code == 400


def test_put_me_merges_overrides(app_and_db):
    app, token = app_and_db
    client = TestClient(app)

    # add google without removing existing confluence override
    resp = client.put(
        "/api/v1/config/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"knowledge_source": {"google": ["drive:folder/demo"]}},
    )
    assert resp.status_code == 200

    eff = client.get(
        "/api/v1/config/me/effective", headers={"Authorization": f"Bearer {token}"}
    ).json()
    assert eff["knowledge_source"]["confluence"] == ["team"]
    assert eff["knowledge_source"]["google"] == ["drive:folder/demo"]


def test_me_effective_is_cached_and_invalidated_on_put(app_and_db, monkeypatch):
    # Enable in-memory cache (singleton) for this test.
    monkeypatch.setenv("CONFIG_CACHE_BACKEND", "memory")
    monkeypatch.setenv("CONFIG_CACHE_TTL_SECONDS", "300")
    from src.core.config_cache import reset_config_cache

    reset_config_cache()

    app, token = app_and_db
    client = TestClient(app)

    import src.services.config_service_rds as csr

    calls = {"lineage": 0, "configs": 0}
    orig_lineage = csr.get_lineage_nodes
    orig_configs = csr.get_node_configs

    def wrapped_lineage(*args, **kwargs):
        calls["lineage"] += 1
        return orig_lineage(*args, **kwargs)

    def wrapped_configs(*args, **kwargs):
        calls["configs"] += 1
        return orig_configs(*args, **kwargs)

    monkeypatch.setattr(csr, "get_lineage_nodes", wrapped_lineage)
    monkeypatch.setattr(csr, "get_node_configs", wrapped_configs)

    # First call populates cache
    r1 = client.get(
        "/api/v1/config/me/effective", headers={"Authorization": f"Bearer {token}"}
    )
    assert r1.status_code == 200
    assert calls["lineage"] == 1
    assert calls["configs"] == 1

    # Second call should hit cache (no additional DB lineage/config reads)
    r2 = client.get(
        "/api/v1/config/me/effective", headers={"Authorization": f"Bearer {token}"}
    )
    assert r2.status_code == 200
    assert calls["lineage"] == 1
    assert calls["configs"] == 1

    # PUT bumps org epoch => effective cache key changes => recompute
    p = client.put(
        "/api/v1/config/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"knowledge_source": {"google": ["drive:folder/demo"]}},
    )
    assert p.status_code == 200

    r3 = client.get(
        "/api/v1/config/me/effective", headers={"Authorization": f"Bearer {token}"}
    )
    assert r3.status_code == 200
    assert calls["lineage"] == 2
    assert calls["configs"] == 2


def test_me_effective_accepts_oidc(monkeypatch):
    # Enable OIDC auth for team endpoints
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pub = key.public_key()
    jwk = jwt.algorithms.RSAAlgorithm.to_jwk(pub)
    jwks = {"keys": [dict(**__import__("json").loads(jwk), kid="test-kid")]}

    monkeypatch.setenv("TEAM_AUTH_MODE", "oidc")
    monkeypatch.setenv("OIDC_ENABLED", "1")
    monkeypatch.setenv("OIDC_ISSUER", "https://issuer.example")
    monkeypatch.setenv("OIDC_AUDIENCE", "opensre-config-service")
    monkeypatch.setenv("OIDC_JWKS_JSON", __import__("json").dumps(jwks))
    monkeypatch.setenv("OIDC_ORG_ID_CLAIM", "org_id")
    monkeypatch.setenv("OIDC_TEAM_NODE_ID_CLAIM", "team_node_id")

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
        headers={"kid": "test-kid"},
    )

    # sqlite in-memory
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)

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
        s.commit()

    from src.api.routes import config_me

    def override_get_db():
        with SessionLocal() as s:
            yield s

    app = create_app()
    app.dependency_overrides[config_me.get_db] = override_get_db

    client = TestClient(app)
    resp = client.get(
        "/api/v1/config/me/effective", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["knowledge_source"]["grafana"] == ["org"]
    assert body["knowledge_source"]["confluence"] == ["team"]
