"""Vanity-rep logic: cached config, the durable tracker mirror, and the pure diff.

No discord here — the cog grants/revokes the actual role and reads presences; this
module owns the config and the tracker set. ``reconcile_targets`` keeps all the
set math here so the cog is the only layer that touches Discord."""

from __future__ import annotations

from src.core.cache import TTLCache
from src.database.session import get_session
from src.modules.vanity.repository import VanityRepository

_NO_CONFIG = object()
_config_cache: TTLCache = TTLCache(ttl_seconds=300)  # guild_id -> VanityConfig | _NO_CONFIG


# ── config (cached read-through; setters invalidate) ───────────────────────────

async def get_config(guild_id: int):
    cached = _config_cache.get(guild_id)
    if cached is not None:
        return None if cached is _NO_CONFIG else cached
    async with get_session() as session:
        cfg = await VanityRepository(session).get_config(guild_id)
    _config_cache.set(guild_id, cfg if cfg is not None else _NO_CONFIG)
    return cfg


async def _set(guild_id: int, **fields) -> None:
    async with get_session() as session:
        cfg = await VanityRepository(session).get_or_create_config(guild_id)
        for key, value in fields.items():
            setattr(cfg, key, value)
    _config_cache.invalidate(guild_id)


async def set_enabled(guild_id: int, value: bool) -> None:
    await _set(guild_id, enabled=value)


async def set_role(guild_id: int, role_id: int | None) -> None:
    await _set(guild_id, role_id=role_id)


async def set_channel(guild_id: int, channel_id: int | None) -> None:
    await _set(guild_id, channel_id=channel_id)


async def set_message(guild_id: int, template: str | None) -> None:
    await _set(guild_id, message_template=template)


# ── trackers ───────────────────────────────────────────────────────────────────

async def add_tracker(guild_id: int, user_id: int) -> None:
    async with get_session() as session:
        await VanityRepository(session).add_tracker(guild_id, user_id)


async def remove_tracker(guild_id: int, user_id: int) -> bool:
    async with get_session() as session:
        return await VanityRepository(session).remove_tracker(guild_id, user_id)


async def get_active_ids(guild_id: int) -> set[int]:
    async with get_session() as session:
        return await VanityRepository(session).active_ids(guild_id)


async def active_count(guild_id: int) -> int:
    async with get_session() as session:
        return await VanityRepository(session).active_count(guild_id)


async def clear_trackers(guild_id: int) -> int:
    async with get_session() as session:
        return await VanityRepository(session).clear(guild_id)


async def reconcile_targets(guild_id: int, live_ids: set[int]) -> tuple[set[int], set[int]]:
    """Pure set math vs the stored set: returns (to_grant, to_revoke)."""
    stored = await get_active_ids(guild_id)
    return (live_ids - stored, stored - live_ids)
