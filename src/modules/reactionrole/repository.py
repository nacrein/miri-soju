"""Data access for reaction roles."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models.reactionrole import ReactionRole


class ReactionRoleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, guild_id: int, message_id: int, emoji: str, role_id: int) -> None:
        existing = await self.role_for(message_id, emoji)
        if existing is None:
            self.session.add(ReactionRole(
                guild_id=guild_id, message_id=message_id, emoji=emoji, role_id=role_id
            ))

    async def role_for(self, message_id: int, emoji: str) -> int | None:
        stmt = select(ReactionRole.role_id).where(
            ReactionRole.message_id == message_id, ReactionRole.emoji == emoji
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def remove(self, message_id: int, emoji: str) -> bool:
        stmt = delete(ReactionRole).where(
            ReactionRole.message_id == message_id, ReactionRole.emoji == emoji
        )
        return ((await self.session.execute(stmt)).rowcount or 0) > 0

    async def list(self, guild_id: int) -> list[ReactionRole]:
        stmt = select(ReactionRole).where(ReactionRole.guild_id == guild_id)
        return list((await self.session.execute(stmt)).scalars().all())

    async def clear(self, guild_id: int) -> int:
        stmt = delete(ReactionRole).where(ReactionRole.guild_id == guild_id)
        return (await self.session.execute(stmt)).rowcount or 0
