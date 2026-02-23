"""In-memory read cache for mem pack."""
from __future__ import annotations

import threading
import time
from typing import Any

from .config import _get_config

_read_cache: dict[str, tuple[Any, float]] = {}
_read_cache_lock = threading.Lock()


def _cache_get(key: str) -> Any | None:
    """Get a cached read result, or None if missing/expired."""
    config = _get_config()
    if config.read_cache_max_size == 0:
        return None
    with _read_cache_lock:
        entry = _read_cache.get(key)
        if entry is None:
            return None
        row, ts = entry
        if config.read_cache_ttl_seconds > 0 and (time.monotonic() - ts) > config.read_cache_ttl_seconds:
            del _read_cache[key]
            return None
        return row


def _cache_put(key: str, row: Any) -> None:
    """Store a read result in the cache, evicting oldest if full."""
    config = _get_config()
    if config.read_cache_max_size == 0:
        return
    with _read_cache_lock:
        # Evict oldest entries if at capacity (and this is a new key)
        if key not in _read_cache and len(_read_cache) >= config.read_cache_max_size:
            # Remove the oldest entry by timestamp
            oldest_key = min(_read_cache, key=lambda k: _read_cache[k][1])
            del _read_cache[oldest_key]
        _read_cache[key] = (row, time.monotonic())


def _cache_invalidate(topic: str | None = None, id: str | None = None) -> None:
    """Invalidate cache entries matching a topic (prefix) or id."""
    with _read_cache_lock:
        if id:
            # Can't map id back to topic key, so clear entire cache
            _read_cache.clear()
            return
        if topic:
            # Prefix invalidation: remove topic and any children
            keys_to_remove = [
                k
                for k in _read_cache
                if k == f"topic:{topic}" or k.startswith(f"topic:{topic}/")
            ]
            for k in keys_to_remove:
                del _read_cache[k]
            return
        # No filter: clear everything
        _read_cache.clear()


def cache_clear(
    *,
    topic: str | None = None,
) -> str:
    """Clear the in-memory read cache.

    Args:
        topic: Clear only entries under this topic prefix. If omitted, clears the entire cache.

    Returns:
        Confirmation message with number of evicted entries.

    Example:
        mem.cache_clear()
        mem.cache_clear(topic="docs/")
    """
    # Perform count and invalidation under one lock to avoid TOCTOU race.
    # Inline the invalidation logic here instead of calling _cache_invalidate
    # which also acquires _read_cache_lock (non-reentrant).
    with _read_cache_lock:
        before = len(_read_cache)
        if topic:
            keys_to_remove = [
                k for k in _read_cache
                if k == f"topic:{topic}" or k.startswith(f"topic:{topic}/")
            ]
            for k in keys_to_remove:
                del _read_cache[k]
        else:
            _read_cache.clear()
        after = len(_read_cache)
    evicted = before - after
    scope = f"topic '{topic}'" if topic else "all"
    return f"Cache cleared ({scope}): {evicted} entries evicted, {after} remaining"


__all__ = [
    "_cache_get",
    "_cache_invalidate",
    "_cache_put",
    "_read_cache",
    "_read_cache_lock",
    "cache_clear",
]
