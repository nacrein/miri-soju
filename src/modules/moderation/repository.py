"""Data access for moderation warnings (infractions)."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models.infraction import Infraction
from src.database.models.jail import JailedMember, ModerationConfig


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

    async def get_jail_role(self, guild_id: int) -> int | None:
        cfg = await self.session.get(ModerationConfig, guild_id)
        return cfg.jail_role_id if cfg else None

    async def set_jail_role(self, guild_id: int, role_id: int) -> None:
        cfg = await self.session.get(ModerationConfig, guild_id)
        if cfg is None:
            self.session.add(ModerationConfig(guild_id=guild_id, jail_role_id=role_id))
        else:
            cfg.jail_role_id = role_id

    async def add_jailed(self, guild_id: int, user_id: int, prior_roles: list[int]) -> None:
        self.session.add(JailedMember(guild_id=guild_id, user_id=user_id, prior_roles=prior_roles))

    async def pop_jailed(self, guild_id: int, user_id: int) -> list[int] | None:
        stmt = select(JailedMember).where(
            JailedMember.guild_id == guild_id, JailedMember.user_id == user_id
        )
        entry = (await self.session.execute(stmt)).scalar_one_or_none()
        if entry is None:
            return None
        roles = list(entry.prior_roles)
        await self.session.delete(entry)
        return roles

    async def list_jailed(self, guild_id: int) -> list[int]:
        stmt = select(JailedMember.user_id).where(JailedMember.guild_id == guild_id)
        return [row[0] for row in (await self.session.execute(stmt)).all()]
