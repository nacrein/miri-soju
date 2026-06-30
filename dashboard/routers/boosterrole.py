"""Booster-role config endpoints (per-guild BoosterRoleConfig row)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from dashboard.deps import require_guild
from dashboard.schemas import BoosterRoleConfigIn, BoosterRoleConfigOut
from src.database.session import get_session
from src.modules.boosterrole.repository import BoosterRoleRepository

router = APIRouter(prefix="/guilds/{guild_id}/boosterrole", tags=["boosterrole"])


def _to_out(cfg) -> BoosterRoleConfigOut:
    return BoosterRoleConfigOut(
        enabled=cfg.enabled,
        hoist_above=cfg.hoist_above,
        anchor_role_id=str(cfg.anchor_role_id) if cfg.anchor_role_id else None,
    )


@router.get("", response_model=BoosterRoleConfigOut)
async def get_config(guild_id: int = Depends(require_guild)) -> BoosterRoleConfigOut:
    async with get_session() as session:
        cfg = await BoosterRoleRepository(session).get_or_create_config(guild_id)
        return _to_out(cfg)


@router.put("", response_model=BoosterRoleConfigOut)
async def update_config(
    body: BoosterRoleConfigIn, guild_id: int = Depends(require_guild)
) -> BoosterRoleConfigOut:
    async with get_session() as session:
        cfg = await BoosterRoleRepository(session).get_or_create_config(guild_id)
        cfg.enabled = body.enabled
        cfg.hoist_above = body.hoist_above
        cfg.anchor_role_id = int(body.anchor_role_id) if body.anchor_role_id else None
        return _to_out(cfg)
