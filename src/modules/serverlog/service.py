"""Server-log logic: config management and log dispatch.

Guild config is cached (read-through with a TTL) since it's read on every logged
event but changes rarely. Config writes invalidate the cache so changes take
effect immediately. Audit data stays in each server's own channel and is never
centrally stored. The cog builds the event embeds; this module resolves the
target channel id (``resolve_log_channel``) and the cog performs the send. A thin
``log_event`` wrapper remains for other modules that route mod-action embeds here.
"""

from __future__ import annotations

import logging

import discord

from src.core.cache import TTLCache
from src.database.models.guild import GuildConfig
from src.database.session import get_session
from src.modules.serverlog.repository import GuildConfigRepository

log = logging.getLogger(__name__)

_NO_CONFIG = object()
# guild_id -> GuildConfig | _NO_CONFIG (sentinel when the guild has no config row).
_config_cache: TTLCache = TTLCache(ttl_seconds=300)

_CATEGORY_FLAG = {
    "join": "log_joins",
    "leave": "log_leaves",
    "msg_delete": "log_message_delete",
    "msg_edit": "log_message_edit",
    "mod": "log_mod_actions",
}


async def _load_config(guild_id: int) -> GuildConfig | None:
    """Read-through: cache first, database on miss. Negative-caches a missing row."""
    cached = _config_cache.get(guild_id)
    if cached is not None:
        return None if cached is _NO_CONFIG else cached
    async with get_session() as session:
        repo = GuildConfigRepository(session)
        config = await repo.get(guild_id)
    _config_cache.set(guild_id, config if config is not None else _NO_CONFIG)
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

async def resolve_log_channel(guild_id: int, category: str) -> int | None:
    """Return the log channel id if logging + this category's toggle are on, else None.

    Discord-free: the cog resolves the channel and sends the embed itself.
    """
    config = await _load_config(guild_id)
    if config is None or config.log_channel_id is None:
        return None
    if not getattr(config, _CATEGORY_FLAG[category]):
        return None
    return config.log_channel_id


async def log_event(
    bot: discord.Client, guild_id: int, embed: discord.Embed, category: str
) -> None:
    """Post an embed to the guild's log channel if logging + the toggle are on.

    Kept for other modules (automod/moderation/vanity) that route mod-action
    embeds here; the serverlog cog's own listeners use ``resolve_log_channel``.
    """
    channel_id = await resolve_log_channel(guild_id, category)
    if channel_id is None:
        return
    channel = bot.get_channel(channel_id)
    if not isinstance(channel, discord.TextChannel):
        return
    try:
        await channel.send(embed=embed)
    except discord.HTTPException:
        pass
