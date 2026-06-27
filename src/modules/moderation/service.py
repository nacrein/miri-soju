"""Moderation logic: duration parsing, case records, immune list, and temp roles.

No discord here — the cog performs the ban/kick/timeout, the target hierarchy
check, and all embed rendering. This module only raises errors and returns values.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.core.cache import TTLCache
from src.core.errors import BotError
from src.database.models.case import ModCase
from src.database.session import get_session
from src.modules.moderation.repository import ModerationRepository

_DURATION_UNITS = {"s": 1, "m": 60, "h": 3600, "d": 86400}
_MAX_TIMEOUT = timedelta(days=28)  # Discord's hard limit


class ModerationError(BotError):
    """A moderation action that can't proceed; message shown to the user."""


def parse_duration(text: str, max_delta: timedelta = _MAX_TIMEOUT) -> timedelta:
    """Parse '10m', '2h', '1d' into a timedelta, bounded by max_delta."""
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
    if delta > max_delta:
        raise ModerationError(f"Duration can't exceed {max_delta.days} days.")
    return delta


# ── cases: warnings, notes, and logged actions ─────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)


async def add_case(guild_id: int, user_id: int, moderator_id: int, kind: str, reason: str | None = None) -> int:
    """Record a moderation event. Returns the new case id."""
    async with get_session() as session:
        repo = ModerationRepository(session)
        case = ModCase(guild_id=guild_id, user_id=user_id, moderator_id=moderator_id, kind=kind, reason=reason)
        repo.add(case)
        await session.flush()
        return case.id


async def list_warnings(guild_id: int, user_id: int) -> list[ModCase]:
    async with get_session() as session:
        return await ModerationRepository(session).cases_by_kind(guild_id, user_id, "warn")


async def list_notes(guild_id: int, user_id: int) -> list[ModCase]:
    async with get_session() as session:
        return await ModerationRepository(session).cases_by_kind(guild_id, user_id, "note")


async def list_cases(guild_id: int, user_id: int, limit: int = 15, offset: int = 0):
    """Full history for a user, paginated. Returns (rows, total_count)."""
    async with get_session() as session:
        repo = ModerationRepository(session)
        rows = await repo.cases_for_user(guild_id, user_id, limit=limit, offset=offset)
        total = await repo.count_for_user(guild_id, user_id)
        return rows, total


async def delete_case(guild_id: int, case_id: int) -> bool:
    """Delete one case by id (guild-scoped). Returns whether it existed."""
    async with get_session() as session:
        repo = ModerationRepository(session)
        case = await repo.case_by_id(guild_id, case_id)
        if case is None:
            return False
        await repo.delete_case(case)
        return True


async def clear_warnings(guild_id: int, user_id: int) -> int:
    async with get_session() as session:
        return await ModerationRepository(session).delete_cases_by_kind(guild_id, user_id, "warn")


# ── immune list (cached; read before every action) ─────────────────────────

# guild_id -> set of immune target ids (users + roles). Invalidated on change.
_immune_cache: TTLCache[int, set[int]] = TTLCache(ttl_seconds=300)


async def _immune_ids(guild_id: int) -> set[int]:
    cached = _immune_cache.get(guild_id)
    if cached is not None:
        return cached
    async with get_session() as session:
        rows = await ModerationRepository(session).list_immune(guild_id)
    ids = {tid for tid, _is_role in rows}
    _immune_cache.set(guild_id, ids)
    return ids


async def is_immune(guild_id: int, target_id: int, role_ids: list[int]) -> bool:
    immune = await _immune_ids(guild_id)
    return target_id in immune or any(rid in immune for rid in role_ids)


async def add_immune(guild_id: int, target_id: int, is_role: bool) -> None:
    async with get_session() as session:
        await ModerationRepository(session).add_immune(guild_id, target_id, is_role)
    _immune_cache.invalidate(guild_id)


async def remove_immune(guild_id: int, target_id: int) -> bool:
    async with get_session() as session:
        removed = await ModerationRepository(session).remove_immune(guild_id, target_id)
    _immune_cache.invalidate(guild_id)
    return removed


async def list_immune(guild_id: int) -> list[tuple[int, bool]]:
    async with get_session() as session:
        return await ModerationRepository(session).list_immune(guild_id)


# ── temp roles ──────────────────────────────────────────────────────────────

async def add_temprole(guild_id: int, user_id: int, role_id: int, expires_at: datetime) -> None:
    async with get_session() as session:
        await ModerationRepository(session).add_temprole(guild_id, user_id, role_id, expires_at)


async def due_temproles():
    """Temp roles whose time has passed. Returns [(id, guild_id, user_id, role_id), ...]."""
    async with get_session() as session:
        return await ModerationRepository(session).due_temproles(_now())


async def delete_temprole(entry_id: int) -> None:
    async with get_session() as session:
        await ModerationRepository(session).delete_temprole(entry_id)


async def remove_temprole(guild_id: int, user_id: int, role_id: int) -> int:
    async with get_session() as session:
        return await ModerationRepository(session).delete_temprole_for(guild_id, user_id, role_id)


async def list_temproles(guild_id: int):
    async with get_session() as session:
        return await ModerationRepository(session).list_temproles(guild_id)


# ── jail storage ────────────────────────────────────────────────────────────

async def set_jail_role(guild_id: int, role_id: int) -> None:
    async with get_session() as session:
        await ModerationRepository(session).set_jail_role(guild_id, role_id)


async def get_jail_role(guild_id: int) -> int | None:
    async with get_session() as session:
        return await ModerationRepository(session).get_jail_role(guild_id)


async def store_jailed(guild_id: int, user_id: int, prior_roles: list[int]) -> None:
    async with get_session() as session:
        await ModerationRepository(session).add_jailed(guild_id, user_id, prior_roles)


async def release_jailed(guild_id: int, user_id: int) -> list[int] | None:
    async with get_session() as session:
        return await ModerationRepository(session).pop_jailed(guild_id, user_id)


async def jailed_members(guild_id: int) -> list[int]:
    async with get_session() as session:
        return await ModerationRepository(session).list_jailed(guild_id)
