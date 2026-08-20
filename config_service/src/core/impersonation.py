from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional

DEFAULT_IMPERSONATION_JWT_AUDIENCE = "opensre-agent-runtime"
LEGACY_IMPERSONATION_JWT_AUDIENCE = "opensre-config-service"


def get_impersonation_jwt_secret() -> str:
    secret = (os.getenv("IMPERSONATION_JWT_SECRET") or "").strip()
    if not secret:
        raise RuntimeError("IMPERSONATION_JWT_SECRET is not set")
    return secret


def get_impersonation_jwt_audience() -> str:
    aud = (
        os.getenv("IMPERSONATION_JWT_AUDIENCE") or DEFAULT_IMPERSONATION_JWT_AUDIENCE
    ).strip()
    return aud or DEFAULT_IMPERSONATION_JWT_AUDIENCE


def accept_legacy_impersonation_jwt_audience() -> bool:
    return (
        os.getenv("IMPERSONATION_JWT_ACCEPT_LEGACY_AUDIENCE", "0") or "0"
    ).strip() == "1"


def get_impersonation_ttl_seconds() -> int:
    try:
        return int(os.getenv("IMPERSONATION_TOKEN_TTL_SECONDS", "900"))
    except Exception:
        return 900


def mint_team_impersonation_token(
    *,
    org_id: str,
    team_node_id: str,
    actor_subject: str,
    actor_email: Optional[str],
    ttl_seconds: Optional[int] = None,
) -> tuple[str, int, str]:
    """
    Mint a short-lived JWT that can be used as a team-scoped bearer token.

    This token is intended for server-to-server flows (e.g. orchestrator -> agent -> config_service),
    and should never be stored as a long-lived credential.
    """
    try:
        import jwt  # PyJWT
    except Exception as e:
        raise RuntimeError("Impersonation tokens require PyJWT to be installed") from e

    now = int(time.time())
    ttl = ttl_seconds if ttl_seconds is not None else get_impersonation_ttl_seconds()
    exp = now + max(60, int(ttl))  # enforce a minimum TTL to avoid clock-skew footguns
    jti = __import__("uuid").uuid4().hex

    claims: Dict[str, Any] = {
        "iss": "opensre-config-service",
        # Dedicated audience to reduce cross-service token reuse.
        # This token is intended to be used by the agent runtime when calling config_service.
        "aud": get_impersonation_jwt_audience(),
        "sub": actor_subject,
        "email": actor_email,
        "org_id": org_id,
        "team_node_id": team_node_id,
        "ifx_kind": "team_impersonation",
        "scope": ["team:read"],
        "iat": now,
        "exp": exp,
        "jti": jti,
    }

    token = jwt.encode(claims, get_impersonation_jwt_secret(), algorithm="HS256")
    return str(token), exp, jti


def verify_team_impersonation_token(token: str) -> Dict[str, Any]:
    """Verify the impersonation JWT and return claims."""
    try:
        import jwt  # PyJWT
    except Exception as e:
        raise RuntimeError("Impersonation tokens require PyJWT to be installed") from e

    audiences = [get_impersonation_jwt_audience()]
    if accept_legacy_impersonation_jwt_audience():
        audiences.append(LEGACY_IMPERSONATION_JWT_AUDIENCE)

    last_err: Optional[Exception] = None
    claims = None
    for aud in audiences:
        try:
            claims = jwt.decode(
                token,
                key=get_impersonation_jwt_secret(),
                algorithms=["HS256"],
                audience=aud,
                issuer="opensre-config-service",
                options={
                    "require": [
                        "exp",
                        "iat",
                        "sub",
                        "org_id",
                        "team_node_id",
                        "ifx_kind",
                        "scope",
                        "jti",
                    ]
                },
            )
            break
        except Exception as e:
            last_err = e
            continue
    if claims is None:
        raise ValueError(f"Invalid impersonation token: {last_err}")

    if claims.get("ifx_kind") != "team_impersonation":
        raise ValueError("Invalid token kind")
    scope = claims.get("scope") or []
    if isinstance(scope, str):
        scope = [scope]
    if "team:read" not in set(scope or []):
        raise ValueError("Missing required scope 'team:read'")
    return dict(claims)
