"""Vanity-rep config endpoints (per-guild VanityConfig row)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from dashboard.deps import require_guild
from dashboard.schemas import VanityConfigIn, VanityConfigOut
from src.database.session import get_session
from src.modules.vanity.repository import VanityRepository

router = APIRouter(prefix="/guilds/{guild_id}/vanity", tags=["vanity"])


def _to_out(cfg) -> VanityConfigOut:
    return VanityConfigOut(
        enabled=cfg.enabled,
        role_id=str(cfg.role_id) if cfg.role_id else None,
        channel_id=str(cfg.channel_id) if cfg.channel_id else None,
        message_template=cfg.message_template,
    )


@router.get("", response_model=VanityConfigOut)
async def get_config(guild_id: int = Depends(require_guild)) -> VanityConfigOut:
    async with get_session() as session:
        cfg = await VanityRepository(session).get_or_create_config(guild_id)
        return _to_out(cfg)


@router.put("", response_model=VanityConfigOut)
async def update_config(
    body: VanityConfigIn, guild_id: int = Depends(require_guild)
) -> VanityConfigOut:
    async with get_session() as session:
        cfg = await VanityRepository(session).get_or_create_config(guild_id)
        cfg.enabled = body.enabled
        cfg.role_id = int(body.role_id) if body.role_id else None
        cfg.channel_id = int(body.channel_id) if body.channel_id else None
        cfg.message_template = body.message_template
        return _to_out(cfg)
