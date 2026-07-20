#!/usr/bin/env python3
"""Shared Jira API client with proxy support.

Supports two Jira flavors in direct mode:
- Jira Cloud: REST API v3, Basic auth (email:api-token), ADF bodies.
- Jira Data Center (self-hosted): REST API v2, Bearer auth (PAT), Wiki Markup bodies.

API version and auth scheme are controlled via env vars (see get_headers / get_base_url).
In proxy mode (production), credentials are injected transparently by the proxy layer.
"""

import base64
import os
from typing import Any

import httpx


def get_config() -> dict[str, str | None]:
    """Get Jira configuration from environment."""
    return {
        "tenant_id": os.getenv("OPENSRE_TENANT_ID", "local"),
        "team_id": os.getenv("OPENSRE_TEAM_ID", "local"),
        "jira_url": os.getenv("JIRA_URL", ""),
    }


def get_base_url() -> str:
    """Get Jira REST API base URL.

    Supports two modes:
    1. Proxy mode (production): Uses JIRA_BASE_URL
    2. Direct mode (testing/local): Uses JIRA_URL + /rest/api/<JIRA_API_VERSION>
       - JIRA_API_VERSION defaults to "3" (Cloud); set to "2" for Jira Data Center.
    """
    proxy_url = os.getenv("JIRA_BASE_URL")
    if proxy_url:
        return proxy_url.rstrip("/")

    jira_url = os.getenv("JIRA_URL")
    if jira_url:
        # Cloud defaults to v3 (ADF); Data Center needs v2 (Wiki Markup).
        # JIRA_API_VERSION lets the caller switch between them without code changes.
        api_version = os.getenv("JIRA_API_VERSION", "3")
        return f"{jira_url.rstrip('/')}/rest/api/{api_version}"

    raise RuntimeError(
        "Either JIRA_BASE_URL (proxy mode) or JIRA_URL (direct mode) must be set."
    )


def get_headers() -> dict[str, str]:
    """Get Jira API headers.

    Auth precedence (direct mode):
    1. Bearer auth (Jira Data Center PAT): used when JIRA_AUTH_SCHEME=bearer OR
       when JIRA_API_TOKEN is set and JIRA_EMAIL is unset. Sends `Authorization: Bearer <token>`.
    2. Basic auth (Jira Cloud): used when both JIRA_EMAIL and JIRA_API_TOKEN are set.
       Sends `Authorization: Basic base64(email:token)`.

    Proxy mode: when no direct creds are present, sends tenant/team context headers
    (or the X-Sandbox-JWT) so the proxy layer can inject credentials.
    """
    config = get_config()
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    email = os.getenv("JIRA_EMAIL")
    api_token = os.getenv("JIRA_API_TOKEN")
    auth_scheme = os.getenv("JIRA_AUTH_SCHEME", "").lower()
    # Explicit bearer scheme, or token-without-email implies Jira Data Center PAT auth.
    use_bearer = auth_scheme == "bearer" or (api_token is not None and not email)

    if auth_scheme == "bearer" and not api_token:
        # Direct DC mode misconfig: bearer requested but no PAT — fail loud instead of
        # silently falling through to proxy/tenant headers (which yields confusing 401s).
        raise RuntimeError(
            "JIRA_AUTH_SCHEME=bearer requires JIRA_API_TOKEN (Data Center PAT)."
        )

    if use_bearer and api_token:
        # Jira Data Center: PAT sent as Bearer token.
        headers["Authorization"] = f"Bearer {api_token}"
    elif email and api_token:
        # Jira Cloud: email + API token sent as Basic auth.
        credentials = base64.b64encode(f"{email}:{api_token}".encode()).decode()
        headers["Authorization"] = f"Basic {credentials}"
    else:
        # Proxy mode: tenant context for credential lookup by the proxy.
        sandbox_jwt = os.getenv("SANDBOX_JWT")
        if sandbox_jwt:
            headers["X-Sandbox-JWT"] = sandbox_jwt
        else:
            headers["X-Tenant-Id"] = config.get("tenant_id") or "local"
            headers["X-Team-Id"] = config.get("team_id") or "local"

    return headers


def get_browse_url() -> str | None:
    """Get the Jira browse URL for constructing issue links."""
    if os.getenv("JIRA_BASE_URL"):
        return None
    jira_url = os.getenv("JIRA_URL", "")
    return jira_url.rstrip("/") if jira_url else None


def jira_request(
    method: str,
    path: str,
    params: dict | None = None,
    json_body: dict | None = None,
) -> dict | list | None:
    """Make a request to Jira REST API."""
    base_url = get_base_url()
    url = f"{base_url}/{path.lstrip('/')}"

    with httpx.Client(timeout=30.0) as client:
        response = client.request(
            method,
            url,
            headers=get_headers(),
            params=params,
            json=json_body,
        )
        response.raise_for_status()
        if response.status_code == 204:
            return None
        return response.json()


def make_adf_text(text: str) -> dict:
    """Create Atlassian Document Format (ADF) for a text block."""
    return {
        "type": "doc",
        "version": 1,
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}],
    }


def make_text_body(text: str) -> dict | str:
    """Build a write body for description/comment fields, picking the right format
    for the configured Jira API version.

    - Jira Cloud (JIRA_API_VERSION=3, default): returns an ADF document (JSON).
    - Jira Data Center (JIRA_API_VERSION=2): returns the plain `text` string,
      interpreted by Jira DC as Wiki Markup. Wiki Markup supports rich formatting
      (`*bold*`, `_italic_`, `||...||` tables, `{code}...{code}`, headings, lists),
      so no formatting capability is lost vs the ADF path (which only wraps the
      input in a single plain paragraph anyway).

    The caller should assign the return value directly to the `description` /
    `body` field of the Jira REST payload — do not wrap it further.
    """
    api_version = os.getenv("JIRA_API_VERSION", "3")
    if api_version == "2":
        # v2 wire format: plain string (Jira Wiki Markup), not ADF JSON.
        return text
    return make_adf_text(text)


def make_assignee_field(assignee: str) -> dict:
    """Build the assignee payload field for the configured Jira API version.

    - Jira Cloud (v3): uses `accountId` (the Atlassian account ID).
    - Jira Data Center (v2): uses `name` (the DC username, e.g. "jane.doe").

    Callers should pass the same identifier they received from the user; the
    correct key is chosen based on JIRA_API_VERSION.
    """
    api_version = os.getenv("JIRA_API_VERSION", "3")
    if api_version == "2":
        return {"name": assignee}
    return {"accountId": assignee}


def extract_adf_text(adf: Any) -> str:
    """Extract plain text from Atlassian Document Format."""
    if isinstance(adf, str):
        return adf
    if not isinstance(adf, dict):
        return ""
    parts = []
    for block in adf.get("content", []):
        for inline in block.get("content", []):
            if inline.get("type") == "text":
                parts.append(inline.get("text", ""))
        parts.append("\n")
    return "\n".join(parts).strip()
