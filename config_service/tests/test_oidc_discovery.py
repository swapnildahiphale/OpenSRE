from types import SimpleNamespace
from unittest.mock import MagicMock
from urllib.parse import parse_qs

import httpx
import pytest
from fastapi import HTTPException
from src.api.routes import security, sso
from src.core.oidc_discovery import OIDCDiscoveryError, discover_oidc

ISSUER = "https://identity.example.com/tenant"
DISCOVERY = ISSUER + "/.well-known/openid-configuration"
AUTHORIZATION = ISSUER + "/login/oauth/authorize"
TOKEN = "https://token.example.com/api/login/oauth/access_token"
USERINFO = ISSUER + "/api/userinfo"
CALLBACK = "http://localhost:3002/api/auth/callback"
METADATA = {
    "issuer": ISSUER,
    "authorization_endpoint": AUTHORIZATION,
    "token_endpoint": TOKEN,
    "userinfo_endpoint": USERINFO,
    "scopes_supported": ["openid", "email", "profile"],
}
CLIENT_SECRET = "example-test-secret"


def mock_http(monkeypatch, handler):
    client_class = httpx.AsyncClient

    def make_client(**kwargs):
        return client_class(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", make_client)


def database(provider_type="oidc"):
    db = MagicMock()
    org = SimpleNamespace(
        issuer=ISSUER,
        provider_type=provider_type,
        provider_name="",
        client_id="application",
        scopes="openid email",
        tenant_id="tenant",
        allowed_domains="example.com",
        email_claim="email",
        name_claim="name",
        groups_claim="groups",
        admin_group=None,
    )
    row = db.query.return_value.filter.return_value.first
    row.side_effect = [org, None]
    return db


@pytest.mark.asyncio
async def test_test_connection_and_public_login_use_advertised_endpoints(monkeypatch):
    def handler(request):
        assert str(request.url) == DISCOVERY
        return httpx.Response(200, json=METADATA)

    mock_http(monkeypatch, handler)
    monkeypatch.setattr(security, "check_org_access", lambda *_: None)
    check = await security.test_sso_config(
        "example", security.SSOTestRequest(), db=database(), admin={}
    )
    login = await security.get_public_sso_config("example", db=database(), discover=True)
    assert check.success
    assert check.metadata == METADATA
    assert login["authorization_endpoint"] == AUTHORIZATION
    assert "token_endpoint" not in login
    assert "userinfo_endpoint" not in login


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("methods", "expected_basic"),
    [(None, True), (["client_secret_post", "client_secret_basic"], False)],
)
async def test_exchange_uses_discovered_token_and_userinfo(monkeypatch, methods, expected_basic):
    seen = []

    def handler(request):
        url = str(request.url)
        seen.append((request.method, url))
        if url == DISCOVERY:
            metadata = METADATA.copy()
            if methods is not None:
                metadata["token_endpoint_auth_methods_supported"] = methods
            return httpx.Response(200, json=metadata)
        if url == TOKEN:
            fields = parse_qs(request.content.decode())
            assert fields["redirect_uri"] == [CALLBACK]
            assert fields["code"] == ["example-code"]
            if expected_basic:
                expected = httpx.BasicAuth("application", CLIENT_SECRET)
                auth_request = next(expected.auth_flow(httpx.Request("POST", TOKEN)))
                assert request.headers["Authorization"] == auth_request.headers["Authorization"]
                assert "client_secret" not in fields
            else:
                assert "Authorization" not in request.headers
                assert fields["client_id"] == ["application"]
                assert fields["client_secret"] == [CLIENT_SECRET]
            return httpx.Response(200, json={"access_token": "fixture-access-token"})
        assert url == USERINFO
        assert request.headers["Authorization"] == "Bearer fixture-access-token"
        return httpx.Response(
            200, json={"sub": "example-subject", "email": "alice@example.com", "name": "Alice"}
        )

    mock_http(monkeypatch, handler)
    monkeypatch.setenv("SSO_CLIENT_SECRET", CLIENT_SECRET)
    monkeypatch.setenv("TOKEN_PEPPER", "fixture-token-pepper-at-least-32-characters")
    db = database()
    result = await sso.exchange_auth_code(
        sso.TokenExchangeRequest(org_id="example", code="example-code", redirect_uri=CALLBACK),
        db=db,
    )
    assert result.email == "alice@example.com"
    assert result.role == "team"
    assert result.session_token
    db.commit.assert_called_once()
    assert seen == [("GET", DISCOVERY), ("POST", TOKEN), ("GET", USERINFO)]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"issuer": "https://elsewhere.example.com"}, "issuer does not match"),
        ({"authorization_endpoint": "/authorize"}, "authorization_endpoint"),
        ({"token_endpoint": "http://identity.example.com/token"}, "token_endpoint"),
        ({"userinfo_endpoint": None}, "userinfo_endpoint"),
        ({"token_endpoint_auth_methods_supported": ["none"]}, "client secret authentication"),
    ],
)
async def test_discovery_rejects_incomplete_or_invalid_metadata(monkeypatch, overrides, message):
    mock_http(monkeypatch, lambda _: httpx.Response(200, json=METADATA | overrides))
    with pytest.raises(OIDCDiscoveryError, match=message):
        await discover_oidc(ISSUER)


@pytest.mark.asyncio
async def test_failed_discovery_does_not_send_credentials_to_guessed_endpoints(monkeypatch):
    seen = []

    def handler(request):
        seen.append((request.method, str(request.url)))
        return httpx.Response(404)

    mock_http(monkeypatch, handler)
    monkeypatch.setenv("SSO_CLIENT_SECRET", CLIENT_SECRET)
    with pytest.raises(HTTPException) as exc:
        await sso.exchange_auth_code(
            sso.TokenExchangeRequest(org_id="example", code="example-code", redirect_uri=CALLBACK),
            db=database(),
        )
    assert exc.value.status_code == 502
    assert seen == [("GET", DISCOVERY)]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("provider", "discover"), [("google", True), ("azure", True), ("oidc", False)]
)
async def test_public_config_skips_discovery_when_not_needed(monkeypatch, provider, discover):
    def unexpected_request(_):
        pytest.fail("Unexpected OIDC discovery request")

    mock_http(monkeypatch, unexpected_request)
    result = await security.get_public_sso_config(
        "example", db=database(provider), discover=discover
    )
    assert result["enabled"]
    assert "authorization_endpoint" not in result
