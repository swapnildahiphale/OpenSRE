import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient


def test_admin_oidc_permissions_derived_from_groups(monkeypatch):
    # Configure OIDC + admin mode
    monkeypatch.setenv("ADMIN_AUTH_MODE", "oidc")
    monkeypatch.setenv("ADMIN_TOKEN", "")  # ensure we don't hit shared token path
    monkeypatch.setenv("OIDC_ENABLED", "1")
    monkeypatch.setenv("OIDC_ISSUER", "https://issuer.example")
    monkeypatch.setenv("OIDC_AUDIENCE", "aud")
    monkeypatch.setenv(
        "OIDC_JWKS_JSON",
        '{"keys":[{"kty":"RSA","kid":"k","use":"sig","n":"AQAB","e":"AQAB"}]}',
    )
    monkeypatch.setenv("OIDC_GROUPS_CLAIM", "groups")
    monkeypatch.setenv("OIDC_ADMIN_GROUP", "opensre-config-admin")

    monkeypatch.setenv("ADMIN_PERMISSIONS_DEFAULT", "admin:read")
    monkeypatch.setenv(
        "ADMIN_GROUP_PERMISSIONS_JSON",
        '{"opensre-config-admin":["admin:provision","admin:agent:run"],"opensre-auditor":"admin:audit"}',
    )

    # Patch verify_oidc_jwt to skip crypto and return claims
    import src.core.oidc as oidc_mod
    from src.api.main import create_app

    def fake_verify(_token: str, *, cfg):  # noqa: ANN001
        return {
            "sub": "user1",
            "email": "user1@example.com",
            "groups": ["opensre-config-admin", "opensre-auditor"],
        }

    monkeypatch.setattr(oidc_mod, "verify_oidc_jwt", fake_verify)

    app = create_app()
    client = TestClient(app)

    r = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer a.b.c"})
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "admin"
    # default + mapped perms
    assert "admin:read" in body["permissions"]
    assert "admin:provision" in body["permissions"]
    assert "admin:agent:run" in body["permissions"]
    assert "admin:audit" in body["permissions"]
