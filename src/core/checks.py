"""Reusable command checks."""

from __future__ import annotations

from discord.ext import commands

from config.settings import get_settings


def _staff_ids() -> set[int]:
    raw = get_settings().staff_ids
    ids = set()
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            ids.add(int(part))
    return ids


async def _is_staff(ctx: commands.Context) -> bool:
    """True for the bot owner or any configured staff id."""
    if await ctx.bot.is_owner(ctx.author):
        return True
    return ctx.author.id in _staff_ids()


def is_staff():
    """Command check: owner or configured staff only."""
    return commands.check(_is_staff)
