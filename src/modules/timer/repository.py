"""Data access for timers."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models.timer import Timer


class TimerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, guild_id, channel_id, interval_seconds, message, next_run) -> None:
        self.session.add(Timer(
            guild_id=guild_id, channel_id=channel_id, interval_seconds=interval_seconds,
            message=message, next_run=next_run,
        ))

    async def for_channel(self, channel_id: int) -> Optional[Timer]:
        stmt = select(Timer).where(Timer.channel_id == channel_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list(self, guild_id: int) -> list[Timer]:
        stmt = select(Timer).where(Timer.guild_id == guild_id)
        return list((await self.session.execute(stmt)).scalars().all())

    async def remove(self, channel_id: int) -> bool:
        stmt = delete(Timer).where(Timer.channel_id == channel_id)
        return ((await self.session.execute(stmt)).rowcount or 0) > 0

    async def due(self, now: datetime) -> list[tuple[int, int, str]]:
        rows = (await self.session.execute(select(Timer).where(Timer.next_run <= now))).scalars().all()
        return [(t.id, t.channel_id, t.message) for t in rows]

    async def reschedule(self, timer_id: int, now: datetime) -> None:
        timer = await self.session.get(Timer, timer_id)
        if timer is not None:
            timer.next_run = now + timedelta(seconds=timer.interval_seconds)
