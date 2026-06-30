"""Reminder storage logic."""

from __future__ import annotations

from datetime import UTC, datetime

from src.database.session import get_session
from src.modules.reminder.repository import ReminderRepository


def _now() -> datetime:
    return datetime.now(UTC)


async def add(user_id, channel_id, guild_id, remind_at, message) -> None:
    async with get_session() as session:
        await ReminderRepository(session).add(user_id, channel_id, guild_id, remind_at, message)


async def for_user(user_id: int):
    async with get_session() as session:
        return await ReminderRepository(session).for_user(user_id)


async def remove(user_id: int, reminder_id: int) -> bool:
    async with get_session() as session:
        return await ReminderRepository(session).remove_for_user(user_id, reminder_id)


async def due():
    async with get_session() as session:
        return await ReminderRepository(session).due(_now())


async def delete_one(reminder_id: int) -> None:
    async with get_session() as session:
        await ReminderRepository(session).delete_one(reminder_id)
