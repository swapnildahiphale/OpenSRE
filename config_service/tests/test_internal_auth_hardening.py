"""Tests for internal auth hardening (bucket B — scoped changes only)."""

from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.api.auth import (
    AdminPrincipal,
    authenticate_admin_request,
    resolve_admin_audit_actor,
)
from src.api.main import create_app
from src.db.config_models import ConfigChangeHistory, NodeConfiguration
from src.db.models import NodeType, OrgNode

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture()
def app_db_admin(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    for table in (
        OrgNode.__table__,
        NodeConfiguration.__table__,
        ConfigChangeHistory.__table__,
    ):
        table.create(engine, checkfirst=True)
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
    return app, SessionLocal


class TestAdminInternalServiceAuth:
    def test_agent_literal_does_not_grant_admin(self, monkeypatch):
        monkeypatch.setenv("INTERNAL_SERVICE_SECRET", "real-secret")
        monkeypatch.setenv("ADMIN_AUTH_MODE", "token")
        with pytest.raises(HTTPException) as exc:
            authenticate_admin_request(
                authorization="",
                x_admin_token="",
                x_internal_service="agent",
            )
        assert exc.value.status_code == 401

    def test_valid_internal_secret_grants_admin(self, monkeypatch):
        monkeypatch.setenv("INTERNAL_SERVICE_SECRET", "real-secret")
        monkeypatch.setenv("ADMIN_AUTH_MODE", "token")
        principal = authenticate_admin_request(
            authorization="",
            x_admin_token="",
            x_internal_service="real-secret",
        )
        assert principal.auth_kind == "internal_service"
        assert principal.subject == "service:real-secret"


class TestResolveAdminAuditActor:
    def test_prefers_email_over_subject(self):
        principal = AdminPrincipal(
            auth_kind="oidc",
            subject="user-123",
            email="admin@example.com",
            claims={},
        )
        assert resolve_admin_audit_actor(principal) == "admin@example.com"

    def test_falls_back_to_subject(self):
        principal = AdminPrincipal(
            auth_kind="admin_token",
            subject="super_admin",
            email=None,
            claims={},
        )
        assert resolve_admin_audit_actor(principal) == "super_admin"


class TestAdminAuditActorFromPrincipal:
    def test_spoofed_x_admin_actor_header_ignored_on_config_write(
        self, app_db_admin
    ):
        app, SessionLocal = app_db_admin
        client = TestClient(app)
        hdr = {
            "Authorization": "Bearer admin-secret",
            "X-Admin-Actor": "spoofed-attacker",
        }

        client.post(
            "/api/v1/admin/orgs/org1/nodes",
            headers=hdr,
            json={"node_id": "teamA", "parent_id": "root", "node_type": "team"},
        )
        resp = client.put(
            "/api/v1/admin/orgs/org1/nodes/teamA/config",
            headers=hdr,
            json={"patch": {"knowledge_source": {"google": ["drive:folder/demo"]}}},
        )
        assert resp.status_code == 200

        with SessionLocal() as session:
            row = session.execute(
                select(NodeConfiguration).where(
                    NodeConfiguration.org_id == "org1",
                    NodeConfiguration.node_id == "teamA",
                )
            ).scalar_one()
            assert row.updated_by == "super_admin"
            assert row.updated_by != "spoofed-attacker"


class TestNextConfigProxyNarrowed:
    def test_no_blanket_api_v1_rewrite(self):
        text = (REPO_ROOT / "web_ui/next.config.ts").read_text()
        assert "/api/v1/:path*" not in text

    def test_local_bff_route_handlers_still_exist(self):
        for rel in (
            "web_ui/src/app/api/v1/tools/metadata/route.ts",
            "web_ui/src/app/api/v1/integrations/schemas/route.ts",
            "web_ui/src/app/api/v1/team/output-config/route.ts",
        ):
            assert (REPO_ROOT / rel).is_file(), rel


class TestRepositoryTokenHashCompareDigest:
    def test_token_hash_checks_use_compare_digest(self):
        text = (REPO_ROOT / "config_service/src/db/repository.py").read_text()
        assert "secrets.compare_digest" in text
        assert "token_hash !=" not in text
