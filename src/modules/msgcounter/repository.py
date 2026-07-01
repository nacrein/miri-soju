"""Reads/writes for the per-(guild, user) message tally.

``bump`` is an upsert that *increments* the counter (create at ``delta`` on first
sight, add ``delta`` thereafter) — the same dual-dialect idiom as
``core/staff_roster`` and ``core/blacklist``. ``by_user`` powers the ``,messages``
lookup: a user's guilds, busiest first.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models.user_message_count import UserMessageCount


class MsgCountRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def bump(self, guild_id: int, user_id: int, delta: int) -> None:
        """Add ``delta`` to (guild, user)'s tally, creating the row if new."""
        if self.session.bind.dialect.name == "postgresql":
            stmt = (
                pg_insert(UserMessageCount)
                .values(guild_id=guild_id, user_id=user_id, count=delta)
                .on_conflict_do_update(
                    index_elements=["guild_id", "user_id"],
                    set_={"count": UserMessageCount.count + delta},
                )
            )
            await self.session.execute(stmt)
        else:
            # Portable fallback (SQLite test harness).
            row = await self.session.get(
                UserMessageCount, {"guild_id": guild_id, "user_id": user_id}
            )
            if row is None:
                self.session.add(
                    UserMessageCount(guild_id=guild_id, user_id=user_id, count=delta)
                )
            else:
                row.count += delta

    async def by_user(self, user_id: int) -> list[tuple[int, int]]:
        """Every guild this user has messaged in as [(guild_id, count), ...], busiest first."""
        stmt = (
            select(UserMessageCount.guild_id, UserMessageCount.count)
            .where(UserMessageCount.user_id == user_id)
            .order_by(UserMessageCount.count.desc())
        )
        return [(int(g), int(c)) for g, c in (await self.session.execute(stmt)).all()]
