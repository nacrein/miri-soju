"""Autorole storage logic. No discord here — just the data."""

from __future__ import annotations

from src.database.session import get_session
from src.modules.autoroles.repository import AutoRoleRepository


async def add(guild_id: int, role_id: int) -> bool:
    async with get_session() as session:
        return await AutoRoleRepository(session).add(guild_id, role_id)


async def remove(guild_id: int, role_id: int) -> bool:
    async with get_session() as session:
        return await AutoRoleRepository(session).remove(guild_id, role_id)


async def list_roles(guild_id: int) -> list[int]:
    async with get_session() as session:
        return await AutoRoleRepository(session).list_roles(guild_id)
