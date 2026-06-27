"""Timer storage logic."""

from __future__ import annotations

from datetime import datetime, timezone

from src.database.session import get_session
from src.modules.timer.repository import TimerRepository


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def add(guild_id, channel_id, interval_seconds, message) -> None:
    async with get_session() as session:
        await TimerRepository(session).add(
            guild_id, channel_id, interval_seconds, message, _now()
        )


async def for_channel(channel_id: int):
    async with get_session() as session:
        return await TimerRepository(session).for_channel(channel_id)


async def all_for(guild_id: int):
    async with get_session() as session:
        return await TimerRepository(session).list(guild_id)


async def remove(channel_id: int) -> bool:
    async with get_session() as session:
        return await TimerRepository(session).remove(channel_id)


async def due_and_reschedule():
    """Return due [(id, channel_id, message)] and reschedule them in one transaction."""
    async with get_session() as session:
        repo = TimerRepository(session)
        now = _now()
        due = await repo.due(now)
        for timer_id, _cid, _msg in due:
            await repo.reschedule(timer_id, now)
        return due
