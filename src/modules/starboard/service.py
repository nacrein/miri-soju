"""Starboard logic: cached per-guild config + (uncached) board-entry bookkeeping.

The config is read on every star reaction but changes rarely, so it is cached
read-through with a TTL (mirroring serverlog/welcome); writes invalidate it. No
discord here — the cog fetches messages, counts reactions, and posts the board."""

from __future__ import annotations

from src.core.cache import TTLCache
from src.database.models.starboard import StarboardConfig, StarboardEntry
from src.database.session import get_session
from src.modules.starboard.repository import StarboardRepository

MIN_THRESHOLD = 1
MAX_THRESHOLD = 50

_NO_CONFIG = object()
_config_cache: TTLCache = TTLCache(ttl_seconds=300)


async def _load_config(guild_id: int) -> StarboardConfig | None:
    cached = _config_cache.get(guild_id)
    if cached is not None:
        return None if cached is _NO_CONFIG else cached
    async with get_session() as session:
        config = await StarboardRepository(session).get_config(guild_id)
    _config_cache.set(guild_id, config if config is not None else _NO_CONFIG)
    return config


async def get_config(guild_id: int) -> StarboardConfig | None:
    """The (cached) config; the cog reads .enabled/.channel_id/.threshold/etc."""
    return await _load_config(guild_id)


async def _mutate(guild_id: int, **values) -> None:
    async with get_session() as session:
        config = await StarboardRepository(session).get_or_create_config(guild_id)
        for field, value in values.items():
            setattr(config, field, value)
    _config_cache.invalidate(guild_id)


async def set_channel(guild_id: int, channel_id: int) -> None:
    await _mutate(guild_id, channel_id=channel_id, enabled=True)


async def set_threshold(guild_id: int, threshold: int) -> int:
    threshold = max(MIN_THRESHOLD, min(threshold, MAX_THRESHOLD))
    await _mutate(guild_id, threshold=threshold)
    return threshold


async def set_emoji(guild_id: int, emoji: str) -> None:
    await _mutate(guild_id, star_emoji=emoji)


async def set_self_star(guild_id: int, value: bool) -> None:
    await _mutate(guild_id, self_star=value)


async def disable(guild_id: int) -> None:
    await _mutate(guild_id, enabled=False)


async def get_summary(guild_id: int) -> dict:
    config = await _load_config(guild_id)
    if config is None:
        return {"enabled": False, "channel_id": None, "threshold": 3,
                "star_emoji": "⭐", "self_star": False}
    return {
        "enabled": config.enabled,
        "channel_id": config.channel_id,
        "threshold": config.threshold,
        "star_emoji": config.star_emoji,
        "self_star": config.self_star,
    }


# ── entries (no caching; one row per boarded message) ────────────────────────

async def get_entry(guild_id: int, message_id: int) -> StarboardEntry | None:
    async with get_session() as session:
        return await StarboardRepository(session).get_entry(guild_id, message_id)


async def upsert_entry(
    guild_id: int, message_id: int, board_message_id: int, star_count: int
) -> None:
    async with get_session() as session:
        await StarboardRepository(session).upsert_entry(
            guild_id, message_id, board_message_id, star_count
        )


async def delete_entry(guild_id: int, message_id: int) -> None:
    async with get_session() as session:
        await StarboardRepository(session).delete_entry(guild_id, message_id)
