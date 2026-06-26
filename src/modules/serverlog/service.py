"""Server-log logic: config management and log dispatch.

Guild config is cached (read-through with a TTL) since it's read on every logged
event but changes rarely. Config writes invalidate the cache so changes take
effect immediately. Audit data stays in each server's own channel and is never
centrally stored. The cog builds the event embeds; this module only routes them.
"""

from __future__ import annotations

import logging

import discord

from src.core.cache import TTLCache
from src.database.models.guild import GuildConfig
from src.database.session import get_session
from src.modules.serverlog.repository import GuildConfigRepository

log = logging.getLogger(__name__)

# guild_id -> GuildConfig (or None when the guild has no config row yet).
_config_cache: TTLCache[int, GuildConfig | None] = TTLCache(ttl_seconds=300)

_CATEGORY_FLAG = {
    "join": "log_joins",
    "leave": "log_leaves",
    "msg_delete": "log_message_delete",
    "msg_edit": "log_message_edit",
    "mod": "log_mod_actions",
}


async def _load_config(guild_id: int) -> GuildConfig | None:
    """Read-through: cache first, database on miss."""
    cached = _config_cache.get(guild_id)
    if cached is not None:
        return cached
    async with get_session() as session:
        repo = GuildConfigRepository(session)
        config = await repo.get(guild_id)
    _config_cache.set(guild_id, config)
    return config


async def get_config_summary(guild_id: int) -> dict:
    """Current logging config for display. Uses the read-through cache."""
    config = await _load_config(guild_id)
    if config is None or config.log_channel_id is None:
        return {"enabled": False}
    return {
        "enabled": True,
        "channel_id": config.log_channel_id,
        "joins": config.log_joins,
        "leaves": config.log_leaves,
        "deletes": config.log_message_delete,
        "edits": config.log_message_edit,
        "mod": config.log_mod_actions,
    }


# ── config operations ───────────────────────────────────────────────────────

async def set_log_channel(guild_id: int, channel_id: int) -> None:
    async with get_session() as session:
        repo = GuildConfigRepository(session)
        config = await repo.get_or_create(guild_id)
        config.log_channel_id = channel_id
    _config_cache.invalidate(guild_id)


async def disable_logging(guild_id: int) -> None:
    async with get_session() as session:
        repo = GuildConfigRepository(session)
        config = await repo.get_or_create(guild_id)
        config.log_channel_id = None
    _config_cache.invalidate(guild_id)


async def set_event_flag(guild_id: int, flag: str, value: bool) -> None:
    async with get_session() as session:
        repo = GuildConfigRepository(session)
        config = await repo.get_or_create(guild_id)
        setattr(config, flag, value)
    _config_cache.invalidate(guild_id)


# ── dispatch ────────────────────────────────────────────────────────────────

async def log_event(
    bot: discord.Client, guild_id: int, embed: discord.Embed, category: str
) -> None:
    """Post an embed to the guild's log channel if logging + the toggle are on."""
    config = await _load_config(guild_id)
    if config is None or config.log_channel_id is None:
        return
    if not getattr(config, _CATEGORY_FLAG[category]):
        return

    channel = bot.get_channel(config.log_channel_id)
    if not isinstance(channel, discord.TextChannel):
        return
    try:
        await channel.send(embed=embed)
    except discord.HTTPException:
        pass
