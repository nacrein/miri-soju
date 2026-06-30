"""Data access for managed webhooks."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models.webhook import ManagedWebhook


class WebhookRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, guild_id: int, channel_id: int, webhook_id: int, short_id: str) -> None:
        self.session.add(ManagedWebhook(
            guild_id=guild_id, channel_id=channel_id, webhook_id=webhook_id, short_id=short_id
        ))

    async def get(self, guild_id: int, short_id: str) -> ManagedWebhook | None:
        stmt = select(ManagedWebhook).where(
            ManagedWebhook.guild_id == guild_id, ManagedWebhook.short_id == short_id
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list(self, guild_id: int) -> list[ManagedWebhook]:
        stmt = select(ManagedWebhook).where(ManagedWebhook.guild_id == guild_id)
        return list((await self.session.execute(stmt)).scalars().all())

    async def remove(self, guild_id: int, short_id: str) -> bool:
        row = await self.get(guild_id, short_id)
        if row is None:
            return False
        await self.session.delete(row)
        return True
