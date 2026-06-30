"""Data access for sticky messages."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models.sticky import StickyMessage


class StickyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert(self, channel_id: int, guild_id: int, content: str) -> None:
        row = await self.session.get(StickyMessage, channel_id)
        if row is None:
            self.session.add(StickyMessage(channel_id=channel_id, guild_id=guild_id, content=content))
        else:
            row.content = content
            row.last_message_id = None

    async def get(self, channel_id: int) -> StickyMessage | None:
        return await self.session.get(StickyMessage, channel_id)

    async def set_last(self, channel_id: int, message_id: int | None) -> None:
        row = await self.session.get(StickyMessage, channel_id)
        if row is not None:
            row.last_message_id = message_id

    async def remove(self, channel_id: int) -> bool:
        row = await self.session.get(StickyMessage, channel_id)
        if row is None:
            return False
        await self.session.delete(row)
        return True

    async def list(self, guild_id: int) -> list[StickyMessage]:
        stmt = select(StickyMessage).where(StickyMessage.guild_id == guild_id)
        return list((await self.session.execute(stmt)).scalars().all())
