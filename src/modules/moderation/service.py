"""Moderation logic: duration parsing and warning records.

No discord here — the cog performs the ban/kick/timeout, the target hierarchy
check, and all embed rendering. This module only raises errors and returns values.
"""

from __future__ import annotations

from datetime import timedelta

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
