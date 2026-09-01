"""SSO Authentication endpoints for OAuth/OIDC login."""

import base64
import json
import os
import secrets
from datetime import datetime, timedelta
from typing import Any, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...core.security import get_token_pepper, hash_token
from ...db.models import SSOConfig, TeamToken
from ...db.session import get_db

router = APIRouter(prefix="/api/v1/auth/sso", tags=["sso"])


class TokenExchangeRequest(BaseModel):
    org_id: str
    code: str
    redirect_uri: str


class TokenExchangeResponse(BaseModel):
    session_token: str
    email: str
    name: Optional[str] = None
    role: str  # admin or team
    org_id: str


def _sso_client_secret() -> str:
    """Entra/OIDC client secret from config-service env (not stored in DB)."""
    return os.getenv("SSO_CLIENT_SECRET", "").strip()


def _generate_token_id() -> str:
    """Generate a unique token ID."""
    return f"sso_{secrets.token_urlsafe(8)}"


def _generate_token_secret() -> str:
    """Generate a secure token secret."""
    return secrets.token_urlsafe(32)


def _sso_token_hash(secret: str) -> str:
    """Hash like mint_team_token so /api/v1/auth/me accepts the cookie."""
    return hash_token(secret, pepper=get_token_pepper())


def _sso_team_node_id() -> str:
    """Team node SSO sessions attach to. Default matches self-hosted `default`."""
    return os.getenv("SSO_DEFAULT_TEAM_NODE_ID", "default")


def _id_token_claims(id_token: Optional[str]) -> dict[str, Any]:
    """Decode ID-token payload without verifying the signature.

    The token just arrived from the provider token endpoint. We only
    read claims as a fallback when Graph userinfo omits email.
    """
    if not id_token or id_token.count(".") < 2:
        return {}
    payload = id_token.split(".")[1]
    padding = "=" * (-len(payload) % 4)
    try:
        decoded = base64.urlsafe_b64decode(payload + padding)
        claims = json.loads(decoded)
        return claims if isinstance(claims, dict) else {}
    except (ValueError, json.JSONDecodeError):
        return {}


def _resolve_sso_email(
    userinfo: dict[str, Any],
    id_token_claims: Optional[dict[str, Any]],
    email_claim: str,
) -> Optional[str]:
    """First identifier that looks like an email.

    Graph userinfo often omits `email` unless the optional claim is set.
    Entra still returns `preferred_username` or `upn` for work accounts.
    """
    sources = [userinfo]
    if id_token_claims:
        sources.append(id_token_claims)
    keys = (email_claim, "email", "preferred_username", "upn")
    for source in sources:
        for key in keys:
            value = source.get(key)
            if isinstance(value, str) and "@" in value:
                return value
    return None


@router.post("/exchange", response_model=TokenExchangeResponse)
async def exchange_auth_code(
    body: TokenExchangeRequest,
    db: Session = Depends(get_db),
):
    """
    Exchange an OAuth authorization code for a session token.

    This endpoint:
    1. Gets the org's SSO config
    2. Exchanges the code for OAuth tokens
    3. Validates the ID token / fetches user info
    4. Creates or updates a token for the user
    5. Returns a session token
    """
    # Get SSO config
    config = (
        db.query(SSOConfig)
        .filter(SSOConfig.org_id == body.org_id, SSOConfig.enabled == True)
        .first()
    )

    if not config:
        raise HTTPException(
            status_code=400, detail="SSO not configured for this organization"
        )

    if not config.client_id:
        raise HTTPException(status_code=400, detail="SSO configuration incomplete")

    client_secret = _sso_client_secret()
    if not client_secret:
        raise HTTPException(
            status_code=500,
            detail="SSO client secret not configured (set SSO_CLIENT_SECRET on config-service)",
        )

    # Build token endpoint URL
    if config.provider_type == "google":
        token_url = "https://oauth2.googleapis.com/token"
        userinfo_url = "https://openidconnect.googleapis.com/v1/userinfo"
    elif config.provider_type == "azure":
        tenant = config.tenant_id or "common"
        token_url = f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
        userinfo_url = "https://graph.microsoft.com/oidc/userinfo"
    else:
        issuer = config.issuer.rstrip("/") if config.issuer else ""
        token_url = f"{issuer}/token"
        userinfo_url = f"{issuer}/userinfo"

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            # Exchange code for tokens
            token_resp = await client.post(
                token_url,
                data={
                    "grant_type": "authorization_code",
                    "code": body.code,
                    "redirect_uri": body.redirect_uri,
                    "client_id": config.client_id,
                    "client_secret": client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

            if token_resp.status_code != 200:
                error_detail = token_resp.text
                raise HTTPException(
                    status_code=400, detail=f"Token exchange failed: {error_detail}"
                )

            tokens = token_resp.json()
            access_token = tokens.get("access_token")
            id_token = tokens.get("id_token")

            if not access_token:
                raise HTTPException(status_code=400, detail="No access token received")

            # Get user info
            userinfo_resp = await client.get(
                userinfo_url,
                headers={"Authorization": f"Bearer {access_token}"},
            )

            if userinfo_resp.status_code != 200:
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to get user info: {userinfo_resp.text}",
                )

            userinfo = userinfo_resp.json()

    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"OAuth request failed: {str(e)}")

    # Extract user details. Prefer Graph userinfo, then ID-token claims.
    email_claim = config.email_claim or "email"
    name_claim = config.name_claim or "name"
    groups_claim = config.groups_claim or "groups"
    token_claims = _id_token_claims(id_token)

    email = _resolve_sso_email(userinfo, token_claims, email_claim)
    name = userinfo.get(name_claim) or token_claims.get(name_claim)
    groups = userinfo.get(groups_claim, [])

    if not email:
        raise HTTPException(status_code=400, detail="No email in user info")

    # Check allowed domains
    if config.allowed_domains:
        allowed = [d.strip().lower() for d in config.allowed_domains.split(",")]
        email_domain = email.split("@")[-1].lower()
        if email_domain not in allowed:
            raise HTTPException(
                status_code=403, detail=f"Email domain '{email_domain}' not allowed"
            )

    # Determine role
    role = "team"  # default
    if config.admin_group:
        if isinstance(groups, list) and config.admin_group in groups:
            role = "admin"

    # Create or find session token for this user
    # Look for existing SSO token for this email
    existing_token = (
        db.query(TeamToken)
        .filter(
            TeamToken.org_id == body.org_id,
            TeamToken.label == f"sso:{email}",
            TeamToken.revoked_at.is_(None),
        )
        .first()
    )

    token_secret = _generate_token_secret()

    # Attach SSO users to the org's working team, not a fake node.
    sso_team_node = _sso_team_node_id()

    if existing_token:
        # Update existing token
        existing_token.token_hash = _sso_token_hash(token_secret)
        existing_token.last_used_at = datetime.utcnow()
        existing_token.expires_at = datetime.utcnow() + timedelta(days=7)
        token_id = existing_token.token_id
    else:
        # Create new token
        token_id = _generate_token_id()
        new_token = TeamToken(
            org_id=body.org_id,
            team_node_id=sso_team_node,
            token_id=token_id,
            token_hash=_sso_token_hash(token_secret),
            label=f"sso:{email}",
            permissions=(
                ["config:read", "config:write", "agent:invoke"]
                if role == "team"
                else [
                    "config:read",
                    "config:write",
                    "tokens:issue",
                    "tokens:revoke",
                    "agent:invoke",
                    "audit:read",
                    "audit:export",
                ]
            ),
            expires_at=datetime.utcnow() + timedelta(days=7),
            issued_by=f"sso:{email}",
        )
        db.add(new_token)

    db.commit()

    # Return session token (token_id.secret format)
    session_token = f"{token_id}.{token_secret}"

    return TokenExchangeResponse(
        session_token=session_token,
        email=email,
        name=name,
        role=role,
        org_id=body.org_id,
    )
