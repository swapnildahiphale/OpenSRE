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
from src.db.base import Base
from src.db.models import NodeType, OrgNode


@pytest.fixture()
def app_db_admin(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)

    monkeypatch.setenv("TOKEN_PEPPER", "test-pepper")
    monkeypatch.setenv("ADMIN_TOKEN", "admin-secret")

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

    from src.api.routes import admin as admin_routes

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
    return app


def test_admin_requires_token(app_db_admin):
    client = TestClient(app_db_admin)
    r = client.post(
        "/api/v1/admin/orgs/org1/nodes",
        json={"node_id": "teamA", "parent_id": "root", "node_type": "team"},
    )
    assert r.status_code in (401, 503)


def test_admin_create_node(app_db_admin):
    client = TestClient(app_db_admin)
    r = client.post(
        "/api/v1/admin/orgs/org1/nodes",
        headers={"Authorization": "Bearer admin-secret"},
        json={
            "node_id": "teamA",
            "parent_id": "root",
            "node_type": "team",
            "name": "Team A",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["node_id"] == "teamA"
    assert body["parent_id"] == "root"
    assert body["node_type"] == "team"


def test_admin_reparent_cycle_rejected(app_db_admin):
    client = TestClient(app_db_admin)
    # root -> teamA
    r = client.post(
        "/api/v1/admin/orgs/org1/nodes",
        headers={"Authorization": "Bearer admin-secret"},
        json={"node_id": "teamA", "parent_id": "root", "node_type": "team"},
    )
    assert r.status_code == 200

    # try reparent root under teamA => cycle
    r2 = client.patch(
        "/api/v1/admin/orgs/org1/nodes/root",
        headers={"Authorization": "Bearer admin-secret"},
        json={"parent_id": "teamA"},
    )
    assert r2.status_code == 400


def test_admin_patch_node_config(app_db_admin):
    client = TestClient(app_db_admin)
    client.post(
        "/api/v1/admin/orgs/org1/nodes",
        headers={"Authorization": "Bearer admin-secret"},
        json={"node_id": "teamA", "parent_id": "root", "node_type": "team"},
    )
    r = client.put(
        "/api/v1/admin/orgs/org1/nodes/teamA/config",
        headers={"Authorization": "Bearer admin-secret"},
        json={"patch": {"knowledge_source": {"google": ["drive:folder/demo"]}}},
    )
    assert r.status_code == 200
    assert r.json()["config"]["knowledge_source"]["google"] == ["drive:folder/demo"]


def test_admin_node_effective_and_raw(app_db_admin):
    client = TestClient(app_db_admin)
    hdr = {"Authorization": "Bearer admin-secret"}

    # root -> teamA
    r = client.post(
        "/api/v1/admin/orgs/org1/nodes",
        headers=hdr,
        json={
            "node_id": "teamA",
            "parent_id": "root",
            "node_type": "team",
            "name": "Team A",
        },
    )
    assert r.status_code == 200

    # Set root config
    r_root = client.put(
        "/api/v1/admin/orgs/org1/nodes/root/config",
        headers=hdr,
        json={
            "patch": {
                "knowledge_source": {"google": ["g1"]},
                "mcp_servers": ["root"],
                "alerts": {"disabled": ["a"]},
            }
        },
    )
    assert r_root.status_code == 200

    # Set team config (overrides lists, merges dicts)
    r_team = client.put(
        "/api/v1/admin/orgs/org1/nodes/teamA/config",
        headers=hdr,
        json={
            "patch": {
                "knowledge_source": {"confluence": ["c1"]},
                "mcp_servers": ["team"],
                "alerts": {"disabled": ["b"]},
            }
        },
    )
    assert r_team.status_code == 200

    raw = client.get("/api/v1/admin/orgs/org1/nodes/teamA/raw", headers=hdr)
    assert raw.status_code == 200
    raw_body = raw.json()
    assert [n["node_id"] for n in raw_body["lineage"]] == ["root", "teamA"]
    assert raw_body["configs"]["root"]["mcp_servers"] == ["root"]
    assert raw_body["configs"]["teamA"]["mcp_servers"] == ["team"]

    eff = client.get("/api/v1/admin/orgs/org1/nodes/teamA/effective", headers=hdr)
    assert eff.status_code == 200
    eff_body = eff.json()
    # Lists replace entirely
    assert eff_body["mcp_servers"] == ["team"]
    assert eff_body["alerts"]["disabled"] == ["b"]
    # Dicts merge recursively
    assert eff_body["knowledge_source"]["google"] == ["g1"]
    assert eff_body["knowledge_source"]["confluence"] == ["c1"]

    missing = client.get("/api/v1/admin/orgs/org1/nodes/nope/effective", headers=hdr)
    assert missing.status_code == 404


def test_admin_list_nodes_and_audit(app_db_admin):
    client = TestClient(app_db_admin)
    hdr = {"Authorization": "Bearer admin-secret"}

    # create a team node
    r = client.post(
        "/api/v1/admin/orgs/org1/nodes",
        headers=hdr,
        json={
            "node_id": "teamA",
            "parent_id": "root",
            "node_type": "team",
            "name": "Team A",
        },
    )
    assert r.status_code == 200

    # list nodes includes root + teamA
    nodes = client.get("/api/v1/admin/orgs/org1/nodes", headers=hdr).json()
    ids = {n["node_id"] for n in nodes}
    assert "root" in ids
    assert "teamA" in ids

    # patch config produces audit rows
    r2 = client.put(
        "/api/v1/admin/orgs/org1/nodes/teamA/config",
        headers=hdr,
        json={"patch": {"mcp_servers": ["x"]}},
    )
    assert r2.status_code == 200

    audit = client.get("/api/v1/admin/orgs/org1/nodes/teamA/audit", headers=hdr).json()
    assert len(audit) >= 1
    assert audit[0]["node_id"] == "teamA"
    assert "changed" in audit[0]["diff"]


def test_admin_org_wide_audit_and_export(app_db_admin):
    client = TestClient(app_db_admin)
    hdr = {"Authorization": "Bearer admin-secret"}

    # create two team nodes
    r = client.post(
        "/api/v1/admin/orgs/org1/nodes",
        headers=hdr,
        json={"node_id": "teamA", "parent_id": "root", "node_type": "team"},
    )
    assert r.status_code == 200
    r2 = client.post(
        "/api/v1/admin/orgs/org1/nodes",
        headers=hdr,
        json={"node_id": "teamB", "parent_id": "root", "node_type": "team"},
    )
    assert r2.status_code == 200

    # patch both => audit rows
    p1 = client.put(
        "/api/v1/admin/orgs/org1/nodes/teamA/config",
        headers=hdr,
        json={"patch": {"mcp_servers": ["a"]}},
    )
    assert p1.status_code == 200
    p2 = client.put(
        "/api/v1/admin/orgs/org1/nodes/teamB/config",
        headers=hdr,
        json={"patch": {"mcp_servers": ["b"]}},
    )
    assert p2.status_code == 200

    rows = client.get("/api/v1/admin/orgs/org1/audit?limit=50", headers=hdr).json()
    assert isinstance(rows, list)
    ids = {r["node_id"] for r in rows}
    assert "teamA" in ids
    assert "teamB" in ids

    only_a = client.get(
        "/api/v1/admin/orgs/org1/audit?node_id=teamA&limit=50", headers=hdr
    ).json()
    assert all(r["node_id"] == "teamA" for r in only_a)

    exp = client.get(
        "/api/v1/admin/orgs/org1/audit/export?format=csv&limit=50", headers=hdr
    )
    assert exp.status_code == 200
    assert "text/csv" in (exp.headers.get("content-type") or "")
    assert "org_id,node_id,version,changed_at,changed_by" in exp.text.splitlines()[0]


def test_admin_accepts_oidc_when_enabled(monkeypatch):
    # Generate a test RSA key and inline JWKS
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pub = key.public_key()
    jwk = jwt.algorithms.RSAAlgorithm.to_jwk(pub)
    jwks = {"keys": [dict(**__import__("json").loads(jwk), kid="test-kid")]}

    monkeypatch.setenv("OIDC_ENABLED", "1")
    monkeypatch.setenv("OIDC_ISSUER", "https://issuer.example")
    monkeypatch.setenv("OIDC_AUDIENCE", "opensre-config-service")
    monkeypatch.setenv("OIDC_JWKS_JSON", __import__("json").dumps(jwks))
    monkeypatch.setenv("OIDC_ADMIN_GROUP", "admins")
    monkeypatch.setenv("OIDC_GROUPS_CLAIM", "groups")
    monkeypatch.setenv("ADMIN_AUTH_MODE", "oidc")

    token = jwt.encode(
        {
            "sub": "user1",
            "iss": "https://issuer.example",
            "aud": "opensre-config-service",
            "groups": ["admins"],
            "exp": int(time.time()) + 3600,
        },
        key,
        algorithm="RS256",
        headers={"kid": "test-kid"},
    )

    # in-memory app/db
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
        s.commit()

    from src.api.routes import admin as admin_routes

    def override_get_db():
        with SessionLocal() as s:
            yield s

    app = create_app()
    app.dependency_overrides[admin_routes.get_db] = override_get_db

    client = TestClient(app)
    r = client.post(
        "/api/v1/admin/orgs/org1/nodes",
        headers={"Authorization": f"Bearer {token}"},
        json={"node_id": "teamA", "parent_id": "root", "node_type": "team"},
    )
    assert r.status_code == 200
