"""Server-side CSRF state for GitHub App installation callback."""

import os
import secrets
from typing import Any, Dict, Optional

from src.core.cache import TTLCache

_DEFAULT_TTL_SECONDS = int(os.getenv("GITHUB_INSTALL_STATE_TTL_SECONDS", "600"))

# In-memory one-time state store (sufficient for simple/local single-process mode).
_state_store = TTLCache(ttl_seconds=_DEFAULT_TTL_SECONDS, max_items=500)


def mint_install_state(created_by: str = "") -> str:
    """Mint opaque state and store it until callback validation consumes it."""
    state = secrets.token_urlsafe(32)
    _state_store.set(
        state,
        {"created_by": created_by},
        ttl_seconds=_DEFAULT_TTL_SECONDS,
    )
    return state


def validate_and_consume_install_state(state: Optional[str]) -> bool:
    """
    Validate callback state and consume it (one-time use).

    Returns True when state was present, unexpired, and successfully consumed.
    """
    if not state:
        return False
    entry: Optional[Dict[str, Any]] = _state_store.get(state)
    if entry is None:
        return False
    _state_store.invalidate(state)
    return True


def clear_install_state_store() -> None:
    """Clear all pending install states (used in tests)."""
    _state_store.clear()
