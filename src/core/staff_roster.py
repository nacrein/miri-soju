"""Runtime staff roster: read/write the DB-backed admin & staff tiers.

Lives in core (not the staff feature module) because ``core/checks.py`` gates on
it, and core must not import feature modules. It owns its own database access, the
same way ``core/error_log.py`` does.

Caching: a tiny in-process dict, populated lazily and kept in sync because every
write goes through this module. That is correct for the single-process bot this
runs as. In a SHARDED or MULTI-INSTANCE deployment the cache would drift between
processes (a promote on one shard wouldn't be seen by another until restart); if
this ever shards, drop the cache or wire it into the existing ``cache_sync``
listener the dashboard already uses for cross-process invalidation.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.database.models.staff import StaffMember
from src.database.session import get_session

# discord_id -> 'admin' | 'staff'. A user absent from the map has no DB tier.
_tier_cache: dict[int, str] = {}
_loaded = False


async def _ensure_loaded() -> None:
    global _loaded
    if _loaded:
        return
    async with get_session() as session:
        rows = (await session.execute(select(StaffMember))).scalars().all()
    _tier_cache.clear()
    _tier_cache.update({r.discord_id: r.tier for r in rows})
    _loaded = True


async def get_tier(discord_id: int) -> str | None:
    """The user's DB tier ('admin'/'staff'), or None if they aren't on the roster."""
    await _ensure_loaded()
    return _tier_cache.get(discord_id)


async def is_staff_member(discord_id: int) -> bool:
    """Fresh, uncached check: is this user on the roster at any tier?

    Deliberately bypasses ``_tier_cache``. It exists for OTHER processes — the web
    dashboard runs separately from the bot and never calls this module's writers, so
    it can't trust the bot's in-process cache; a cached read there would miss a
    ``,staff promote`` until restart. A single indexed PK lookup, hit only on
    staff-area access (not per command), so the bot itself keeps using ``get_tier``."""
    async with get_session() as session:
        return await session.get(StaffMember, discord_id) is not None


async def list_roster() -> list[StaffMember]:
    """All roster rows, admins before staff, newest first within a tier."""
    async with get_session() as session:
        stmt = select(StaffMember).order_by(
            # 'admin' sorts before 'staff' alphabetically, which is the order we want.
            StaffMember.tier.asc(), StaffMember.created_at.desc()
        )
        return list((await session.execute(stmt)).scalars().all())


async def set_tier(discord_id: int, tier: str, added_by: int) -> None:
    """Grant (or move) a user to ``tier``. Upserts: one row per user."""
    async with get_session() as session:
        if session.bind.dialect.name == "postgresql":
            stmt = (
                pg_insert(StaffMember)
                .values(discord_id=discord_id, tier=tier, added_by=added_by)
                .on_conflict_do_update(
                    index_elements=["discord_id"],
                    set_={"tier": tier, "added_by": added_by},
                )
            )
            await session.execute(stmt)
        else:
            # Portable fallback (SQLite test harness).
            row = await session.get(StaffMember, discord_id)
            if row is None:
                session.add(StaffMember(discord_id=discord_id, tier=tier, added_by=added_by))
            else:
                row.tier = tier
                row.added_by = added_by
    _tier_cache[discord_id] = tier


async def remove(discord_id: int) -> bool:
    """Revoke a user's tier. Returns True if a row was removed, False if none existed."""
    async with get_session() as session:
        row = await session.get(StaffMember, discord_id)
        if row is None:
            _tier_cache.pop(discord_id, None)
            return False
        await session.delete(row)
    _tier_cache.pop(discord_id, None)
    return True
