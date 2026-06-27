"""Data access for button roles."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models.buttonrole import ButtonRole


class ButtonRoleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, guild_id, message_id, role_id, label, emoji, style) -> None:
        self.session.add(ButtonRole(
            guild_id=guild_id, message_id=message_id, role_id=role_id,
            label=label, emoji=emoji, style=style,
        ))

    async def for_message(self, message_id: int) -> list[ButtonRole]:
        stmt = select(ButtonRole).where(ButtonRole.message_id == message_id).order_by(ButtonRole.id.asc())
        return list((await self.session.execute(stmt)).scalars().all())

    async def list(self, guild_id: int) -> list[ButtonRole]:
        stmt = select(ButtonRole).where(ButtonRole.guild_id == guild_id)
        return list((await self.session.execute(stmt)).scalars().all())

    async def remove_one(self, message_id: int, index: int) -> ButtonRole | None:
        rows = await self.for_message(message_id)
        if index < 1 or index > len(rows):
            return None
        target = rows[index - 1]
        await self.session.delete(target)
        return target

    async def remove_message(self, message_id: int) -> int:
        stmt = delete(ButtonRole).where(ButtonRole.message_id == message_id)
        return (await self.session.execute(stmt)).rowcount or 0

    async def clear(self, guild_id: int) -> int:
        stmt = delete(ButtonRole).where(ButtonRole.guild_id == guild_id)
        return (await self.session.execute(stmt)).rowcount or 0
