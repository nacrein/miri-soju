"""Data access for vanity rep: the config row and the tracker mirror.

Standard async SQLAlchemy, mirroring ``src/modules/leveling/repository.py``."""

from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models.vanity import VanityConfig, VanityTracker


class VanityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ── config ────────────────────────────────────────────────────────────────

    async def get_config(self, guild_id: int) -> VanityConfig | None:
        return await self.session.get(VanityConfig, guild_id)

    async def get_or_create_config(self, guild_id: int) -> VanityConfig:
        cfg = await self.session.get(VanityConfig, guild_id)
        if cfg is None:
            cfg = VanityConfig(guild_id=guild_id)
            self.session.add(cfg)
            await self.session.flush()
        return cfg

    # ── trackers ──────────────────────────────────────────────────────────────

    async def add_tracker(self, guild_id: int, user_id: int) -> None:
        # Insert inside a savepoint and swallow the unique-violation, so a concurrent
        # grant (presence event racing the reconcile loop) can't raise out of the caller.
        try:
            async with self.session.begin_nested():
                self.session.add(VanityTracker(guild_id=guild_id, user_id=user_id))
        except IntegrityError:
            pass  # another grant already created the row

    async def remove_tracker(self, guild_id: int, user_id: int) -> bool:
        stmt = delete(VanityTracker).where(
            VanityTracker.guild_id == guild_id, VanityTracker.user_id == user_id
        )
        return ((await self.session.execute(stmt)).rowcount or 0) > 0

    async def active_ids(self, guild_id: int) -> set[int]:
        stmt = select(VanityTracker.user_id).where(VanityTracker.guild_id == guild_id)
        return {r[0] for r in (await self.session.execute(stmt)).all()}

    async def active_count(self, guild_id: int) -> int:
        stmt = select(func.count()).select_from(VanityTracker).where(
            VanityTracker.guild_id == guild_id
        )
        return int((await self.session.execute(stmt)).scalar_one())

    async def clear(self, guild_id: int) -> int:
        stmt = delete(VanityTracker).where(VanityTracker.guild_id == guild_id)
        return (await self.session.execute(stmt)).rowcount or 0
