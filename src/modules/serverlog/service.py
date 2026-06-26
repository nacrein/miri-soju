"""Server-log logic: config management, log dispatch, event embeds.

Guild config is cached (read-through with a TTL) since it's read on every logged
event but changes rarely. Config writes invalidate the cache so changes take
effect immediately. Audit data stays in each server's own channel and is never
centrally stored.
"""

from __future__ import annotations

import logging

import discord

from src.core.cache import TTLCache
from src.core.emojis import Emojis
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


# ── event embed builders ────────────────────────────────────────────────────

def _truncate(text: str, limit: int = 1000) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def join_embed(member: discord.Member) -> discord.Embed:
    e = discord.Embed(
        description=f"{Emojis.JOIN} {member.mention} joined", color=discord.Color.green()
    )
    e.set_author(name=str(member), icon_url=member.display_avatar.url)
    e.add_field(name="Account created", value=discord.utils.format_dt(member.created_at, "R"))
    e.set_footer(text=f"ID: {member.id}")
    e.timestamp = discord.utils.utcnow()
    return e


def leave_embed(member: discord.Member) -> discord.Embed:
    e = discord.Embed(
        description=f"{Emojis.LEAVE} {member.mention} left", color=discord.Color.red()
    )
    e.set_author(name=str(member), icon_url=member.display_avatar.url)
    e.set_footer(text=f"ID: {member.id}")
    e.timestamp = discord.utils.utcnow()
    return e


def message_delete_embed(message: discord.Message) -> discord.Embed:
    e = discord.Embed(
        description=(
            f"{Emojis.MESSAGE_DELETE} Message by {message.author.mention} "
            f"deleted in {message.channel.mention}"
        ),
        color=discord.Color.orange(),
    )
    if message.content:
        e.add_field(name="Content", value=_truncate(message.content), inline=False)
    e.set_footer(text=f"Author ID: {message.author.id}")
    e.timestamp = discord.utils.utcnow()
    return e


def message_edit_embed(before: discord.Message, after: discord.Message) -> discord.Embed:
    # Tighter cap on edits: two fields plus the jump link must stay well under
    # Discord's 6000-char total embed limit.
    e = discord.Embed(
        description=(
            f"{Emojis.MESSAGE_EDIT} Message by {before.author.mention} "
            f"edited in {before.channel.mention}"
        ),
        color=discord.Color.blue(),
    )
    e.add_field(name="Before", value=_truncate(before.content, 900) or "—", inline=False)
    e.add_field(name="After", value=_truncate(after.content, 900) or "—", inline=False)
    e.add_field(name="Jump", value=f"[link]({after.jump_url})", inline=False)
    e.set_footer(text=f"Author ID: {before.author.id}")
    e.timestamp = discord.utils.utcnow()
    return e
