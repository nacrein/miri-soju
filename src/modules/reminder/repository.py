"""Data access for reminders."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models.reminder import Reminder


class ReminderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, user_id, channel_id, guild_id, remind_at, message) -> None:
        self.session.add(Reminder(
            user_id=user_id, channel_id=channel_id, guild_id=guild_id,
            remind_at=remind_at, message=message,
        ))

    async def for_user(self, user_id: int) -> list[Reminder]:
        stmt = select(Reminder).where(Reminder.user_id == user_id).order_by(Reminder.remind_at.asc())
        return list((await self.session.execute(stmt)).scalars().all())

    async def remove_for_user(self, user_id: int, reminder_id: int) -> bool:
        stmt = delete(Reminder).where(Reminder.id == reminder_id, Reminder.user_id == user_id)
        return ((await self.session.execute(stmt)).rowcount or 0) > 0

    async def due(self, now: datetime) -> list[tuple[int, int, int, str]]:
        rows = (await self.session.execute(select(Reminder).where(Reminder.remind_at <= now))).scalars().all()
        return [(r.id, r.user_id, r.channel_id, r.message) for r in rows]

    async def delete_one(self, reminder_id: int) -> None:
        await self.session.execute(delete(Reminder).where(Reminder.id == reminder_id))
