from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Optional

from src.core.cache import TTLCache


class CacheBackend:
    """Minimal cache backend interface used by config resolution."""

    def get_str(self, key: str) -> Optional[str]:
        raise NotImplementedError

    def set_str(self, key: str, value: str, ttl_seconds: int) -> None:
        raise NotImplementedError

    def get_int(self, key: str, default: int = 0) -> int:
        raw = self.get_str(key)
        if raw is None:
            return default
        try:
            return int(raw)
        except Exception:
            return default

    def incr_int(self, key: str) -> int:
        raise NotImplementedError

    def get_json(self, key: str) -> Optional[Any]:
        raw = self.get_str(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except Exception:
            return None

    def set_json(self, key: str, value: Any, ttl_seconds: int) -> None:
        self.set_str(
            key,
            json.dumps(value, separators=(",", ":"), sort_keys=True),
            ttl_seconds=ttl_seconds,
        )


class InMemoryCacheBackend(CacheBackend):
    def __init__(self, *, ttl_seconds: int, max_items: int = 5000):
        # Use a single TTL store; epoch is cached "long enough" and will reset on restart (acceptable).
        self._ttl = TTLCache(ttl_seconds=ttl_seconds, max_items=max_items)

    def get_str(self, key: str) -> Optional[str]:
        v = self._ttl.get(key)
        if v is None:
            return None
        if isinstance(v, str):
            return v
        return None

    def set_str(self, key: str, value: str, ttl_seconds: int) -> None:
        self._ttl.set(key, value, ttl_seconds=ttl_seconds)

    def incr_int(self, key: str) -> int:
        cur = self.get_int(key, default=0)
        nxt = cur + 1
        # keep epoch around for a day in memory; TTL is still bounded to avoid unbounded growth
        self.set_str(key, str(nxt), ttl_seconds=24 * 3600)
        return nxt


class RedisCacheBackend(CacheBackend):
    def __init__(self, *, redis_url: str):
        # Lazy import so runtime doesn't require redis unless enabled.
        import redis  # type: ignore

        self._client = redis.Redis.from_url(redis_url, decode_responses=True)

    def get_str(self, key: str) -> Optional[str]:
        v = self._client.get(key)
        return v if isinstance(v, str) else None

    def set_str(self, key: str, value: str, ttl_seconds: int) -> None:
        # Use SETEX so values expire and keys don't accumulate indefinitely.
        self._client.setex(key, ttl_seconds, value)

    def incr_int(self, key: str) -> int:
        return int(self._client.incr(key))


@dataclass(frozen=True)
class ConfigCache:
    backend: CacheBackend
    ttl_seconds: int

    def org_epoch_key(self, org_id: str) -> str:
        return f"cfg:org:{org_id}:epoch"

    def effective_key(self, org_id: str, team_node_id: str, epoch: int) -> str:
        return f"cfg:effective:{org_id}:{team_node_id}:{epoch}"

    def raw_key(self, org_id: str, team_node_id: str, epoch: int) -> str:
        return f"cfg:raw:{org_id}:{team_node_id}:{epoch}"

    def get_org_epoch(self, org_id: str) -> int:
        return self.backend.get_int(self.org_epoch_key(org_id), default=0)

    def bump_org_epoch(self, org_id: str) -> int:
        return self.backend.incr_int(self.org_epoch_key(org_id))


_CONFIG_CACHE_SINGLETON: Optional[ConfigCache] = None


def get_config_cache() -> Optional[ConfigCache]:
    """Create a process-wide cache singleton based on env vars.

    Caching is DISABLED by default to avoid cache invalidation bugs.
    Enable only if you have high config read load and understand the tradeoffs.

    Env:
      - CONFIG_CACHE_BACKEND: "none" (default), "memory", "redis"
      - CONFIG_CACHE_TTL_SECONDS: default 30
      - REDIS_URL: required if backend=redis
    """
    global _CONFIG_CACHE_SINGLETON
    if _CONFIG_CACHE_SINGLETON is not None:
        return _CONFIG_CACHE_SINGLETON

    backend_kind = (os.getenv("CONFIG_CACHE_BACKEND") or "none").strip().lower()
    ttl = int((os.getenv("CONFIG_CACHE_TTL_SECONDS") or "30").strip())
    ttl = max(1, min(ttl, 3600))

    if backend_kind == "none":
        _CONFIG_CACHE_SINGLETON = None
        return None

    if backend_kind == "redis":
        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            raise RuntimeError("CONFIG_CACHE_BACKEND=redis requires REDIS_URL")
        _CONFIG_CACHE_SINGLETON = ConfigCache(
            backend=RedisCacheBackend(redis_url=redis_url), ttl_seconds=ttl
        )
        return _CONFIG_CACHE_SINGLETON

    # memory cache
    _CONFIG_CACHE_SINGLETON = ConfigCache(
        backend=InMemoryCacheBackend(ttl_seconds=ttl), ttl_seconds=ttl
    )
    return _CONFIG_CACHE_SINGLETON


def reset_config_cache() -> None:
    """Reset the process-wide cache singleton (useful for tests)."""
    global _CONFIG_CACHE_SINGLETON
    _CONFIG_CACHE_SINGLETON = None
