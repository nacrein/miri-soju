"""Reusable command checks and the owner > admin > staff tier model.

Tiers, highest first:
  * owner — discord.py's built-in owner. Not stored anywhere.
  * admin — DB-backed (``staff_members`` tier 'admin'); the serious economy/roster
    powers. Granted by the owner via ,staff promote <user> admin.
  * staff — DB-backed tier 'staff', OR a legacy ``STAFF_IDS`` env id (see below).

Legacy STAFF_IDS: ids configured in the env still count as the ``staff`` tier, so
existing deployments keep working with no migration step. They are *not* backfilled
into ``staff_members`` — they resolve purely through the fallback here. To manage
someone at runtime (promote/demote), add them to the DB roster instead.
"""

from __future__ import annotations

from discord.ext import commands

from config.settings import get_settings
from src.core import staff_roster


def _staff_ids() -> set[int]:
    raw = get_settings().staff_ids
    ids = set()
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            ids.add(int(part))
    return ids


async def _tier_of(bot: commands.Bot, user) -> str | None:
    """The user's effective tier: 'owner' > 'admin' > 'staff' > None."""
    if await bot.is_owner(user):
        return "owner"
    db_tier = await staff_roster.get_tier(user.id)
    if db_tier:
        return db_tier
    if user.id in _staff_ids():  # legacy STAFF_IDS bootstrap -> staff tier
        return "staff"
    return None


async def _is_admin(ctx: commands.Context) -> bool:
    """True for the bot owner or any admin-tier member."""
    return (await _tier_of(ctx.bot, ctx.author)) in ("owner", "admin")


async def _is_staff(ctx: commands.Context) -> bool:
    """True for the bot owner, admins, or any staff-tier member.

    A strict superset of the historical owner-or-STAFF_IDS check, so no command
    that used to allow a caller now denies them.
    """
    return (await _tier_of(ctx.bot, ctx.author)) in ("owner", "admin", "staff")


def is_admin():
    """Command check: owner or admin tier only (serious economy/roster powers)."""
    return commands.check(_is_admin)


def is_staff():
    """Command check: owner, admin, or staff tier."""
    return commands.check(_is_staff)
