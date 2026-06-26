"""Data access for moderation warnings (infractions)."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models.infraction import Infraction


class ModerationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def add(self, infraction: Infraction) -> None:
        self.session.add(infraction)

    async def for_user(self, guild_id: int, user_id: int) -> list[Infraction]:
        stmt = (
            select(Infraction)
            .where(Infraction.guild_id == guild_id, Infraction.user_id == user_id)
            .order_by(Infraction.created_at.desc(), Infraction.id.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def by_id(self, guild_id: int, infraction_id: int) -> Optional[Infraction]:
        # Scoped to the guild so one server can't touch another's records.
        stmt = select(Infraction).where(
            Infraction.id == infraction_id, Infraction.guild_id == guild_id
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def delete_for_user(self, guild_id: int, user_id: int) -> int:
        stmt = delete(Infraction).where(
            Infraction.guild_id == guild_id, Infraction.user_id == user_id
        )
        result = await self.session.execute(stmt)
        return result.rowcount or 0
