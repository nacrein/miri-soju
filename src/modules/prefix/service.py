"""Per-guild command prefix: cached lookup + setter. The global default is ','."""

from __future__ import annotations

from src.core.cache import TTLCache
from src.database.models.guild import GuildConfig
from src.database.session import get_session

DEFAULT_PREFIX = ","

# guild_id -> resolved prefix. Read on every message, so it's cached; the bare
# default is cached too, so unconfigured guilds don't hit the DB each message.
_cache: TTLCache[int, str] = TTLCache(ttl_seconds=300)


async def get_prefix(guild_id: int) -> str:
    """The guild's prefix, or the default if it hasn't set one."""
    cached = _cache.get(guild_id)
    if cached is not None:
        return cached
    async with get_session() as session:
        cfg = await session.get(GuildConfig, guild_id)
        prefix = cfg.prefix if cfg and cfg.prefix else DEFAULT_PREFIX
    _cache.set(guild_id, prefix)
    return prefix


async def set_prefix(guild_id: int, prefix: str) -> None:
    """Set this guild's prefix, creating its config row if needed."""
    async with get_session() as session:
        cfg = await session.get(GuildConfig, guild_id)
        if cfg is None:
            session.add(GuildConfig(guild_id=guild_id, prefix=prefix))
        else:
            cfg.prefix = prefix
    _cache.invalidate(guild_id)
