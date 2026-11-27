"""Resolve the endpoints used by OpenSRE's Custom OIDC login."""

from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx


class OIDCDiscoveryError(ValueError):
    """The provider did not return usable OIDC metadata."""


@dataclass(frozen=True)
class OIDCMetadata:
    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    userinfo_endpoint: str
    token_endpoint_auth_method: str
    scopes_supported: tuple[str, ...]


def _https_url(value: object, field: str, *, allow_query: bool = True) -> str:
    if isinstance(value, str) and not any(c.isspace() or c == "\\" for c in value):
        try:
            parts = urlsplit(value)
            # Access port here to reject malformed authorities as well.
            _ = parts.port
            if (
                parts.scheme == "https"
                and parts.hostname
                and parts.username is None
                and "#" not in value
                and (allow_query or "?" not in value)
            ):
                return value
        except ValueError:
            pass
    raise OIDCDiscoveryError(f"Invalid or missing HTTPS URL for {field}")


async def discover_oidc(issuer: str | None) -> OIDCMetadata:
    """Fetch and validate discovery metadata for the configured issuer."""
    issuer = _https_url(issuer.strip() if issuer else None, "issuer", allow_query=False)
    discovery_url = f"{issuer.rstrip('/')}/.well-known/openid-configuration"

    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
            response = await client.get(discovery_url)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPStatusError as exc:
        raise OIDCDiscoveryError(
            f"OIDC discovery returned HTTP {exc.response.status_code}"
        ) from exc
    except (httpx.RequestError, ValueError) as exc:
        raise OIDCDiscoveryError("Unable to read OIDC discovery metadata") from exc

    if not isinstance(data, dict) or data.get("issuer") != issuer:
        raise OIDCDiscoveryError("OIDC discovery issuer does not match the configured issuer")

    authorization_endpoint = _https_url(
        data.get("authorization_endpoint"), "authorization_endpoint"
    )
    token_endpoint = _https_url(data.get("token_endpoint"), "token_endpoint")
    # OpenSRE currently requires UserInfo to establish the session identity.
    userinfo_endpoint = _https_url(data.get("userinfo_endpoint"), "userinfo_endpoint")

    methods = data.get("token_endpoint_auth_methods_supported", ["client_secret_basic"])
    if not isinstance(methods, list):
        raise OIDCDiscoveryError("Invalid token endpoint authentication methods")
    # Keep the existing client-secret POST behavior when advertised.
    method = next((m for m in ("client_secret_post", "client_secret_basic") if m in methods), None)
    if method is None:
        raise OIDCDiscoveryError("OIDC provider does not support client secret authentication")

    scopes = data.get("scopes_supported")
    return OIDCMetadata(
        issuer=issuer,
        authorization_endpoint=authorization_endpoint,
        token_endpoint=token_endpoint,
        userinfo_endpoint=userinfo_endpoint,
        token_endpoint_auth_method=method,
        scopes_supported=tuple(s for s in scopes if isinstance(s, str))
        if isinstance(scopes, list)
        else (),
    )
