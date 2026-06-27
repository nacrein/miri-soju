"""Reaction-role storage logic."""

from __future__ import annotations

from src.database.session import get_session
from src.modules.reactionrole.repository import ReactionRoleRepository


async def add(guild_id: int, message_id: int, emoji: str, role_id: int) -> None:
    async with get_session() as session:
        await ReactionRoleRepository(session).add(guild_id, message_id, emoji, role_id)


async def role_for(message_id: int, emoji: str) -> int | None:
    async with get_session() as session:
        return await ReactionRoleRepository(session).role_for(message_id, emoji)


async def remove(message_id: int, emoji: str) -> bool:
    async with get_session() as session:
        return await ReactionRoleRepository(session).remove(message_id, emoji)


async def all_for(guild_id: int):
    async with get_session() as session:
        return await ReactionRoleRepository(session).list(guild_id)


async def clear(guild_id: int) -> int:
    async with get_session() as session:
        return await ReactionRoleRepository(session).clear(guild_id)
