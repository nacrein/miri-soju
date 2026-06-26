"""Moderation logic: target safety checks, duration parsing, action embeds.

No Discord side effects here; the cog performs the actual ban/kick/timeout.
"""

from __future__ import annotations

from datetime import timedelta

import discord

from src.core.emojis import Emojis
from src.core.errors import BotError
from src.database.models.infraction import Infraction
from src.database.session import get_session
from src.modules.moderation.repository import ModerationRepository

_DURATION_UNITS = {"s": 1, "m": 60, "h": 3600, "d": 86400}
_MAX_TIMEOUT = timedelta(days=28)  # Discord's hard limit


class ModerationError(BotError):
    """A moderation action that can't proceed; message shown to the user."""


def parse_duration(text: str) -> timedelta:
    """Parse '10m', '2h', '1d' into a timedelta. Enforces Discord's 28-day cap."""
    text = text.strip().lower()
    if not text or text[-1] not in _DURATION_UNITS:
        raise ModerationError("Duration must look like `10m`, `2h`, or `1d`.")
    try:
        amount = int(text[:-1])
    except ValueError:
        raise ModerationError("Duration must be a number followed by s, m, h, or d.")
    if amount <= 0:
        raise ModerationError("Duration must be positive.")
    delta = timedelta(seconds=amount * _DURATION_UNITS[text[-1]])
    if delta > _MAX_TIMEOUT:
        raise ModerationError("Timeout can't exceed 28 days.")
    return delta


def check_target(
    ctx: "discord.ext.commands.Context",
    target: discord.Member,
    *,
    require_bot_higher: bool = True,
) -> None:
    """Raise ModerationError if the moderator (or bot) can't action this member.

    require_bot_higher=False for actions the bot doesn't enact on Discord (e.g. warn).
    """
    if target == ctx.author:
        raise ModerationError("You can't target yourself.")
    if target == ctx.guild.me:
        raise ModerationError("I can't target myself.")
    if target.id == ctx.guild.owner_id:
        raise ModerationError("You can't target the server owner.")
    # Moderator hierarchy (the guild owner bypasses this).
    if ctx.author.id != ctx.guild.owner_id and target.top_role >= ctx.author.top_role:
        raise ModerationError("That member is equal to or above you in the role hierarchy.")
    # Bot hierarchy: the bot's top role must be above the target's.
    if require_bot_higher and target.top_role >= ctx.guild.me.top_role:
        raise ModerationError("That member is above me in the role hierarchy.")


_ACTION_ICONS = {
    "Ban": Emojis.BAN, "Unban": Emojis.UNBAN, "Kick": Emojis.KICK,
    "Timeout": Emojis.TIMEOUT, "Untimeout": Emojis.UNTIMEOUT, "Purge": Emojis.PURGE,
}


def action_embed(
    action: str,
    moderator: discord.abc.User,
    target: discord.abc.User,
    reason: str,
) -> discord.Embed:
    """Build the mod-action embed posted to the audit channel."""
    icon = _ACTION_ICONS.get(action.split()[0], Emojis.SHIELD)
    e = discord.Embed(title=f"{icon} {action}", color=discord.Color.dark_red())
    e.add_field(name="Member", value=f"{target} (`{target.id}`)", inline=False)
    e.add_field(name="Moderator", value=str(moderator), inline=False)
    e.add_field(name="Reason", value=reason, inline=False)
    e.timestamp = discord.utils.utcnow()
    return e


# ── warnings (per-guild, recorded for mods to act on manually) ──────────────

async def add_warning(guild_id: int, user_id: int, moderator_id: int, reason: str) -> int:
    """Record a warning. Returns the new warning's id."""
    async with get_session() as session:
        repo = ModerationRepository(session)
        infraction = Infraction(
            guild_id=guild_id, user_id=user_id, moderator_id=moderator_id, reason=reason
        )
        repo.add(infraction)
        await session.flush()
        return infraction.id


async def list_warnings(guild_id: int, user_id: int) -> list[Infraction]:
    async with get_session() as session:
        repo = ModerationRepository(session)
        return await repo.for_user(guild_id, user_id)


async def delete_warning(guild_id: int, infraction_id: int) -> bool:
    """Delete one warning by id (scoped to the guild). Returns whether it existed."""
    async with get_session() as session:
        repo = ModerationRepository(session)
        infraction = await repo.by_id(guild_id, infraction_id)
        if infraction is None:
            return False
        await session.delete(infraction)
        return True


async def clear_warnings(guild_id: int, user_id: int) -> int:
    """Delete all of a user's warnings in this guild. Returns the count removed."""
    async with get_session() as session:
        repo = ModerationRepository(session)
        return await repo.delete_for_user(guild_id, user_id)
