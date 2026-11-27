from types import SimpleNamespace

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.api.auth import AdminPrincipal
from src.api.routes import audit as audit_routes


def _audit_app(admin: AdminPrincipal) -> FastAPI:
    app = FastAPI()
    app.include_router(audit_routes.router, prefix="/api/v1/admin/orgs/{org_id}")

    def override_admin() -> AdminPrincipal:
        return admin

    def override_db():
        yield None

    app.dependency_overrides[audit_routes.require_admin] = override_admin
    app.dependency_overrides[audit_routes.get_db] = override_db
    return app


def test_org_admin_denied_foreign_unified_audit_list():
    admin = AdminPrincipal(
        auth_kind="org_admin_token",
        subject="org_admin:org1",
        email=None,
        claims={},
        org_id="org1",
    )
    client = TestClient(_audit_app(admin))

    r = client.get("/api/v1/admin/orgs/org2/unified-audit")
    assert r.status_code == 403
    assert "org1" in r.json()["detail"]


def test_org_admin_denied_foreign_unified_audit_export():
    admin = AdminPrincipal(
        auth_kind="org_admin_token",
        subject="org_admin:org1",
        email=None,
        claims={},
        org_id="org1",
    )
    client = TestClient(_audit_app(admin))

    r = client.get("/api/v1/admin/orgs/org2/unified-audit/export")
    assert r.status_code == 403
    assert "org1" in r.json()["detail"]


def test_org_admin_denied_foreign_agent_runs_list():
    admin = AdminPrincipal(
        auth_kind="org_admin_token",
        subject="org_admin:org1",
        email=None,
        claims={},
        org_id="org1",
    )
    client = TestClient(_audit_app(admin))

    r = client.get("/api/v1/admin/orgs/org2/unified-audit/agent-runs")
    assert r.status_code == 403


def test_org_admin_can_list_own_unified_audit(monkeypatch):
    admin = AdminPrincipal(
        auth_kind="org_admin_token",
        subject="org_admin:org1",
        email=None,
        claims={},
        org_id="org1",
    )
    client = TestClient(_audit_app(admin))

    monkeypatch.setattr(audit_routes.repository, "list_unified_audit", lambda *a, **k: ([], 0))
    monkeypatch.setattr(audit_routes.repository, "list_org_nodes", lambda *a, **k: [])

    r = client.get("/api/v1/admin/orgs/org1/unified-audit")
    assert r.status_code == 200
    body = r.json()
    assert body["events"] == []
    assert body["total"] == 0


def test_super_admin_can_access_any_org_unified_audit(monkeypatch):
    admin = AdminPrincipal(
        auth_kind="admin_token",
        subject="super_admin",
        email=None,
        claims={},
        org_id=None,
    )
    client = TestClient(_audit_app(admin))

    monkeypatch.setattr(audit_routes.repository, "list_unified_audit", lambda *a, **k: ([], 0))
    monkeypatch.setattr(audit_routes.repository, "list_org_nodes", lambda *a, **k: [])

    for org_id in ("org1", "org2"):
        r = client.get(f"/api/v1/admin/orgs/{org_id}/unified-audit")
        assert r.status_code == 200
        assert r.json()["total"] == 0


def test_super_admin_can_export_any_org_unified_audit(monkeypatch):
    admin = AdminPrincipal(
        auth_kind="admin_token",
        subject="super_admin",
        email=None,
        claims={},
        org_id=None,
    )
    client = TestClient(_audit_app(admin))

    monkeypatch.setattr(audit_routes.repository, "list_unified_audit", lambda *a, **k: ([], 0))

    for org_id in ("org1", "org2"):
        exp = client.get(f"/api/v1/admin/orgs/{org_id}/unified-audit/export")
        assert exp.status_code == 200
        assert "text/csv" in (exp.headers.get("content-type") or "")


def test_org_admin_denied_foreign_agent_run_create():
    admin = AdminPrincipal(
        auth_kind="org_admin_token",
        subject="org_admin:org1",
        email=None,
        claims={},
        org_id="org1",
    )
    client = TestClient(_audit_app(admin))

    r = client.post(
        "/api/v1/admin/orgs/org1/unified-audit/agent-runs",
        json={
            "run_id": "run-1",
            "org_id": "org2",
            "trigger_source": "web",
            "agent_name": "investigator",
        },
    )
    assert r.status_code == 403


def test_org_admin_denied_foreign_agent_run_complete(monkeypatch):
    admin = AdminPrincipal(
        auth_kind="org_admin_token",
        subject="org_admin:org1",
        email=None,
        claims={},
        org_id="org1",
    )
    client = TestClient(_audit_app(admin))

    foreign_run = SimpleNamespace(org_id="org2")
    monkeypatch.setattr(
        audit_routes.repository,
        "get_agent_run",
        lambda *a, **k: foreign_run,
    )

    complete_called = []

    def _fail_if_complete(*args, **kwargs):
        complete_called.append(True)
        return None

    monkeypatch.setattr(
        audit_routes.repository,
        "complete_agent_run",
        _fail_if_complete,
    )

    r = client.patch(
        "/api/v1/admin/orgs/org1/unified-audit/agent-runs/run-foreign",
        json={
            "run_id": "run-foreign",
            "status": "completed",
        },
    )
    assert r.status_code == 403
    assert "org1" in r.json()["detail"]
    assert complete_called == []
