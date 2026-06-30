"""Autoroles endpoints — the list of role ids auto-granted on join.

A list managed via add/remove (like leveling's rewards); every mutation returns
the full list so the panel refreshes in one round-trip."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from dashboard.deps import require_guild
from dashboard.schemas import AutoroleIdIn, AutorolesConfigOut
from src.database.session import get_session
from src.modules.autoroles.repository import AutoRoleRepository

router = APIRouter(prefix="/guilds/{guild_id}/autoroles", tags=["autoroles"])


async def _load(session, guild_id: int) -> AutorolesConfigOut:
    roles = await AutoRoleRepository(session).list_roles(guild_id)
    return AutorolesConfigOut(roles=[str(r) for r in roles])


@router.get("", response_model=AutorolesConfigOut)
async def get_config(guild_id: int = Depends(require_guild)) -> AutorolesConfigOut:
    async with get_session() as session:
        return await _load(session, guild_id)


@router.post("", response_model=AutorolesConfigOut)
async def add_role(
    body: AutoroleIdIn, guild_id: int = Depends(require_guild)
) -> AutorolesConfigOut:
    async with get_session() as session:
        await AutoRoleRepository(session).add(guild_id, int(body.role_id))
        return await _load(session, guild_id)


@router.delete("/{role_id}", response_model=AutorolesConfigOut)
async def remove_role(
    role_id: int, guild_id: int = Depends(require_guild)
) -> AutorolesConfigOut:
    async with get_session() as session:
        await AutoRoleRepository(session).remove(guild_id, role_id)
        return await _load(session, guild_id)
