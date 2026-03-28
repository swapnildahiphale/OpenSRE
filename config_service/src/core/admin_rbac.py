from __future__ import annotations

import json
import os
from typing import Any, Optional


def _split_csv(value: str) -> list[str]:
    parts = [p.strip() for p in (value or "").split(",")]
    return [p for p in parts if p]


def _load_group_permission_map() -> dict[str, list[str]]:
    """
    Load a mapping of OIDC group -> permissions list.

    Env:
      ADMIN_GROUP_PERMISSIONS_JSON='{"opensre-admin":["admin:*"],"opensre-provisioner":["admin:provision"]}'
    """
    raw = (os.getenv("ADMIN_GROUP_PERMISSIONS_JSON") or "").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except Exception:
        return {}
    out: dict[str, list[str]] = {}
    if isinstance(data, dict):
        for k, v in data.items():
            if not isinstance(k, str):
                continue
            if isinstance(v, list):
                out[k] = [str(x) for x in v if str(x).strip()]
            elif isinstance(v, str):
                out[k] = _split_csv(v)
    return out


def resolve_admin_permissions(
    *,
    auth_kind: str,
    oidc_claims: Optional[dict[str, Any]] = None,
    oidc_groups_claim: str = "groups",
) -> list[str]:
    """
    Resolve admin permissions for /api/v1/auth/me.

    Defaults:
    - ADMIN_PERMISSIONS_DEFAULT: "admin:*" (preserves current behavior)
    - ADMIN_GROUP_PERMISSIONS_JSON: optional fine-grained mapping.
    """
    # Break-glass tokens keep full access by default.
    if auth_kind == "admin_token":
        return ["admin:*"]

    default_perms = _split_csv(os.getenv("ADMIN_PERMISSIONS_DEFAULT", "admin:*"))
    if not oidc_claims:
        return default_perms

    groups_val = oidc_claims.get(oidc_groups_claim, [])
    groups: list[str] = []
    if isinstance(groups_val, str):
        groups = [groups_val]
    elif isinstance(groups_val, list):
        groups = [str(x) for x in groups_val if str(x).strip()]

    group_map = _load_group_permission_map()
    perms: list[str] = list(default_perms)
    for g in groups:
        perms.extend(group_map.get(g, []))

    # de-dupe stable
    seen = set()
    out: list[str] = []
    for p in perms:
        p = str(p).strip()
        if not p or p in seen:
            continue
        seen.add(p)
        out.append(p)
    return out
