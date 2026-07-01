"""Blacklist reads/writes: the bot-wide and economy-only user gates.

Lives in core (like ``staff_roster``) so ``core/bot.py``'s global check and the
Economy cog can both reach it without core importing a feature module. Owns its
own database access.

Caching: two in-process sets, loaded lazily and kept in sync because every write
goes through here. Correct for a single-process bot; in a sharded/multi-instance
deployment the cache would drift between processes until restart (see the same
note on ``core/staff_roster``).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.database.models.blacklist import Blacklist
from src.database.session import get_session

SCOPES = ("bot", "economy")

_cache: dict[str, set[int]] = {scope: set() for scope in SCOPES}
_loaded = False


async def _ensure_loaded() -> None:
    global _loaded
    if _loaded:
        return
    async with get_session() as session:
        rows = (await session.execute(select(Blacklist))).scalars().all()
    for scope in SCOPES:
        _cache[scope].clear()
    for r in rows:
        _cache.setdefault(r.scope, set()).add(r.discord_id)
    _loaded = True


async def is_blacklisted(discord_id: int, scope: str) -> bool:
    """Whether the user is blacklisted for ``scope`` ('bot' or 'economy')."""
    await _ensure_loaded()
    return discord_id in _cache.get(scope, set())


async def list_scope(scope: str) -> list[Blacklist]:
    """All rows for a scope, newest first."""
    async with get_session() as session:
        stmt = (
            select(Blacklist)
            .where(Blacklist.scope == scope)
            .order_by(Blacklist.created_at.desc())
        )
        return list((await session.execute(stmt)).scalars().all())


async def add(discord_id: int, scope: str, reason: str | None, added_by: int) -> None:
    """Blacklist a user for ``scope``. Upserts, refreshing the reason if it exists."""
    async with get_session() as session:
        if session.bind.dialect.name == "postgresql":
            stmt = (
                pg_insert(Blacklist)
                .values(discord_id=discord_id, scope=scope, reason=reason, added_by=added_by)
                .on_conflict_do_update(
                    index_elements=["discord_id", "scope"],
                    set_={"reason": reason, "added_by": added_by},
                )
            )
            await session.execute(stmt)
        else:
            row = await session.get(Blacklist, {"discord_id": discord_id, "scope": scope})
            if row is None:
                session.add(Blacklist(
                    discord_id=discord_id, scope=scope, reason=reason, added_by=added_by
                ))
            else:
                row.reason = reason
                row.added_by = added_by
    _cache.setdefault(scope, set()).add(discord_id)


async def remove(discord_id: int, scope: str) -> bool:
    """Lift a blacklist. Returns True if a row was removed, False if none existed."""
    async with get_session() as session:
        row = await session.get(Blacklist, {"discord_id": discord_id, "scope": scope})
        if row is None:
            _cache.get(scope, set()).discard(discord_id)
            return False
        await session.delete(row)
    _cache.get(scope, set()).discard(discord_id)
    return True
