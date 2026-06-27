"""Sticky-message storage logic."""

from __future__ import annotations

from src.database.session import get_session
from src.modules.stickymessage.repository import StickyRepository


async def set_sticky(channel_id: int, guild_id: int, content: str) -> None:
    async with get_session() as session:
        await StickyRepository(session).upsert(channel_id, guild_id, content)


async def get_sticky(channel_id: int):
    async with get_session() as session:
        return await StickyRepository(session).get(channel_id)


async def set_last(channel_id: int, message_id: int | None) -> None:
    async with get_session() as session:
        await StickyRepository(session).set_last(channel_id, message_id)


async def remove(channel_id: int) -> bool:
    async with get_session() as session:
        return await StickyRepository(session).remove(channel_id)


async def all_for(guild_id: int):
    async with get_session() as session:
        return await StickyRepository(session).list(guild_id)
