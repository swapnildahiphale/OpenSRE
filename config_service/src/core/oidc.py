from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

from src.core.cache import TTLCache

_jwks_cache = TTLCache(ttl_seconds=300, max_items=16)


@dataclass(frozen=True)
class OIDCConfig:
    issuer: str
    audience: str
    jwks_url: Optional[str]
    jwks_json: Optional[str]
    alg: str
    leeway_seconds: int
    groups_claim: str
    admin_group: str
    org_id_claim: str
    team_node_id_claim: str
    email_claim: str
    subject_claim: str


def load_oidc_config() -> Optional[OIDCConfig]:
    if os.getenv("OIDC_ENABLED", "0") != "1":
        return None

    issuer = os.getenv("OIDC_ISSUER", "")
    audience = os.getenv("OIDC_AUDIENCE", "")
    if not issuer or not audience:
        # OIDC enabled but misconfigured: treat as disabled
        return None

    return OIDCConfig(
        issuer=issuer,
        audience=audience,
        jwks_url=os.getenv("OIDC_JWKS_URL"),
        jwks_json=os.getenv("OIDC_JWKS_JSON"),
        alg=os.getenv("OIDC_ALG", "RS256"),
        leeway_seconds=int(os.getenv("OIDC_LEEWAY_SECONDS", "30")),
        groups_claim=os.getenv("OIDC_GROUPS_CLAIM", "groups"),
        admin_group=os.getenv("OIDC_ADMIN_GROUP", "opensre-config-admin"),
        org_id_claim=os.getenv("OIDC_ORG_ID_CLAIM", "org_id"),
        team_node_id_claim=os.getenv("OIDC_TEAM_NODE_ID_CLAIM", "team_node_id"),
        email_claim=os.getenv("OIDC_EMAIL_CLAIM", "email"),
        subject_claim=os.getenv("OIDC_SUBJECT_CLAIM", "sub"),
    )


def verify_oidc_jwt(token: str, *, cfg: OIDCConfig) -> Dict[str, Any]:
    """Verify an OIDC JWT against the configured JWKS and return claims.

    Supports RS256 by default.
    """
    try:
        import jwt  # PyJWT
    except Exception as e:
        raise RuntimeError("OIDC requires PyJWT to be installed") from e

    header = jwt.get_unverified_header(token)
    kid = header.get("kid")
    if not kid:
        raise ValueError("Missing kid")

    jwks = _get_jwks(cfg)
    key_jwk = None
    for k in jwks.get("keys", []):
        if k.get("kid") == kid:
            key_jwk = k
            break
    if key_jwk is None:
        raise ValueError("Unknown kid")

    key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(key_jwk))
    return jwt.decode(
        token,
        key=key,
        algorithms=[cfg.alg],
        audience=cfg.audience,
        issuer=cfg.issuer,
        options={"require": ["exp", cfg.subject_claim]},
        leeway=cfg.leeway_seconds,
    )


def _get_jwks(cfg: OIDCConfig) -> Dict[str, Any]:
    # Avoid cross-test / cross-config collisions when using inline JWKS_JSON.
    # (Inline JWKS can change between calls even with the same issuer.)
    inline_hash = ""
    if cfg.jwks_json:
        inline_hash = hashlib.sha256(cfg.jwks_json.encode("utf-8")).hexdigest()
    cache_key = (cfg.jwks_url or ("inline:" + inline_hash)) + "|" + (cfg.issuer or "")
    cached = _jwks_cache.get(cache_key)
    if isinstance(cached, dict):
        return cached

    if cfg.jwks_json:
        jwks = json.loads(cfg.jwks_json)
        _jwks_cache.set(cache_key, jwks)
        return jwks

    if not cfg.jwks_url:
        raise ValueError("OIDC_JWKS_URL not configured")

    try:
        import httpx
    except Exception as e:
        raise RuntimeError("OIDC requires httpx to be installed") from e

    with httpx.Client(timeout=3.0) as client:
        resp = client.get(cfg.jwks_url)
        resp.raise_for_status()
        jwks = resp.json()
    _jwks_cache.set(cache_key, jwks)
    return jwks
