"""Tiny in-memory TTL cache. Used for hot, rarely-changing data like guild config."""

from __future__ import annotations

import time
from typing import Generic, TypeVar

K = TypeVar("K")
V = TypeVar("V")

# Module-level sentinel: lets callers tell "no entry / expired" apart from a cached
# None. ``get`` returns None for both; ``get_or_miss`` returns MISS only for an absent
# entry, so a negative result (e.g. "this guild has no config row") can be cached
# without being re-fetched on every call.
MISS: object = object()

# Every cache registers here so cross-process invalidation (see cache_sync) can reach
# all of them by key. Module-level caches live for the process lifetime, so the list
# never needs pruning.
_INSTANCES: list[TTLCache] = []


class TTLCache(Generic[K, V]):
    """Dict with per-entry expiry. Single-process only; see ``cache_sync`` for the
    cross-process invalidation that keeps the dashboard and bot in step."""

    def __init__(self, ttl_seconds: float = 300) -> None:
        self._ttl = ttl_seconds
        self._store: dict[K, tuple[float, V]] = {}
        _INSTANCES.append(self)

    def get(self, key: K) -> V | None:
        value = self.get_or_miss(key)
        return None if value is MISS else value  # type: ignore[return-value]

    def get_or_miss(self, key: K) -> V | object:
        """Like ``get`` but returns the ``MISS`` sentinel for an absent/expired entry,
        so a cached ``None`` is distinguishable from a miss."""
        entry = self._store.get(key)
        if entry is None:
            return MISS
        expires_at, value = entry
        if time.monotonic() >= expires_at:
            self._store.pop(key, None)
            return MISS
        return value

    def set(self, key: K, value: V) -> None:
        self._store[key] = (time.monotonic() + self._ttl, value)

    def invalidate(self, key: K) -> None:
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()


def invalidate_guild(guild_id: int) -> None:
    """Drop ``guild_id`` from every cache. Used by cross-process invalidation
    (cache_sync): per-guild config caches are keyed by guild id, so this clears the
    stale entry; caches keyed by something else simply miss and are unaffected."""
    for cache in _INSTANCES:
        cache.invalidate(guild_id)
