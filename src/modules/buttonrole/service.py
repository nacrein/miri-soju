"""Button-role storage logic."""

from __future__ import annotations

from src.database.session import get_session
from src.modules.buttonrole.repository import ButtonRoleRepository


async def add(guild_id, message_id, role_id, label, emoji, style) -> None:
    async with get_session() as session:
        await ButtonRoleRepository(session).add(guild_id, message_id, role_id, label, emoji, style)


async def for_message(message_id: int):
    async with get_session() as session:
        return await ButtonRoleRepository(session).for_message(message_id)


async def all_for(guild_id: int):
    async with get_session() as session:
        return await ButtonRoleRepository(session).list(guild_id)


async def remove_one(message_id: int, index: int):
    async with get_session() as session:
        return await ButtonRoleRepository(session).remove_one(message_id, index)


async def remove_message(message_id: int) -> int:
    async with get_session() as session:
        return await ButtonRoleRepository(session).remove_message(message_id)


async def clear(guild_id: int) -> int:
    async with get_session() as session:
        return await ButtonRoleRepository(session).clear(guild_id)
