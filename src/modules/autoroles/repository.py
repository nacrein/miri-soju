"""Data access for autoroles."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models.autorole import AutoRole


class AutoRoleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, guild_id: int, role_id: int) -> bool:
        """Insert the pairing; return False if it already existed (the unique guard)."""
        stmt = select(AutoRole.id).where(
            AutoRole.guild_id == guild_id, AutoRole.role_id == role_id
        )
        if (await self.session.execute(stmt)).scalar_one_or_none() is not None:
            return False
        self.session.add(AutoRole(guild_id=guild_id, role_id=role_id))
        return True

    async def remove(self, guild_id: int, role_id: int) -> bool:
        stmt = delete(AutoRole).where(
            AutoRole.guild_id == guild_id, AutoRole.role_id == role_id
        )
        return ((await self.session.execute(stmt)).rowcount or 0) > 0

    async def list_roles(self, guild_id: int) -> list[int]:
        stmt = (
            select(AutoRole.role_id)
            .where(AutoRole.guild_id == guild_id)
            .order_by(AutoRole.id.asc())
        )
        return list((await self.session.execute(stmt)).scalars().all())
