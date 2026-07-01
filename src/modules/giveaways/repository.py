"""Data access for giveaways and their entries."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models.giveaway import Giveaway, GiveawayEntry


class GiveawayRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self, *, guild_id: int, channel_id: int, message_id: int,
        prize: str, winners: int, ends_at: datetime, host_id: int,
    ) -> Giveaway:
        g = Giveaway(
            guild_id=guild_id, channel_id=channel_id, message_id=message_id,
            prize=prize, winners=winners, ends_at=ends_at, host_id=host_id,
        )
        self.session.add(g)
        await self.session.flush()
        return g

    async def get_by_message(self, message_id: int) -> Giveaway | None:
        stmt = select(Giveaway).where(Giveaway.message_id == message_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def due(self, now: datetime) -> list[Giveaway]:
        stmt = select(Giveaway).where(Giveaway.ended.is_(False), Giveaway.ends_at <= now)
        return list((await self.session.execute(stmt)).scalars().all())

    async def active_for(self, guild_id: int) -> list[Giveaway]:
        stmt = (
            select(Giveaway)
            .where(Giveaway.guild_id == guild_id, Giveaway.ended.is_(False))
            .order_by(Giveaway.ends_at.asc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def mark_ended(self, giveaway_id: int) -> None:
        await self.session.execute(
            update(Giveaway).where(Giveaway.id == giveaway_id).values(ended=True)
        )

    async def has_entry(self, giveaway_id: int, user_id: int) -> bool:
        stmt = select(GiveawayEntry.id).where(
            GiveawayEntry.giveaway_id == giveaway_id, GiveawayEntry.user_id == user_id
        )
        return (await self.session.execute(stmt)).scalar_one_or_none() is not None

    async def add_entry(self, giveaway_id: int, user_id: int) -> None:
        self.session.add(GiveawayEntry(giveaway_id=giveaway_id, user_id=user_id))

    async def remove_entry(self, giveaway_id: int, user_id: int) -> None:
        await self.session.execute(delete(GiveawayEntry).where(
            GiveawayEntry.giveaway_id == giveaway_id, GiveawayEntry.user_id == user_id
        ))

    async def entrants(self, giveaway_id: int) -> list[int]:
        stmt = select(GiveawayEntry.user_id).where(GiveawayEntry.giveaway_id == giveaway_id)
        return list((await self.session.execute(stmt)).scalars().all())
