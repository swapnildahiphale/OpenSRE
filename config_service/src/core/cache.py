import time
from typing import Any, Dict, Optional, Tuple


class TTLCache:
    """Simple in-memory TTL cache for single-process deployments."""

    def __init__(self, ttl_seconds: int = 60, max_items: int = 2000):
        self.ttl_seconds = ttl_seconds
        self.max_items = max_items
        self._store: Dict[str, Tuple[float, Any]] = {}

    def get(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if time.time() > expires_at:
            self._store.pop(key, None)
            return None
        return value

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        if len(self._store) >= self.max_items:
            # naive eviction: delete an arbitrary entry
            self._store.pop(next(iter(self._store)), None)
        ttl = self.ttl_seconds if ttl_seconds is None else ttl_seconds
        self._store[key] = (time.time() + ttl, value)

    def invalidate(self, key: str) -> None:
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()
