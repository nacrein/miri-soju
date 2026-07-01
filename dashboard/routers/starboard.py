"""Starboard config endpoints (per-guild StarboardConfig row)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from dashboard.deps import require_guild
from dashboard.schemas import StarboardConfigIn, StarboardConfigOut
from src.database.session import get_session
from src.modules.starboard.repository import StarboardRepository

router = APIRouter(prefix="/guilds/{guild_id}/starboard", tags=["starboard"])


def _to_out(cfg) -> StarboardConfigOut:
    return StarboardConfigOut(
        channel_id=str(cfg.channel_id) if cfg.channel_id else None,
        threshold=cfg.threshold,
        star_emoji=cfg.star_emoji,
        enabled=cfg.enabled,
        self_star=cfg.self_star,
    )


@router.get("", response_model=StarboardConfigOut)
async def get_config(guild_id: int = Depends(require_guild)) -> StarboardConfigOut:
    async with get_session() as session:
        cfg = await StarboardRepository(session).get_or_create_config(guild_id)
        return _to_out(cfg)


@router.put("", response_model=StarboardConfigOut)
async def update_config(
    body: StarboardConfigIn, guild_id: int = Depends(require_guild)
) -> StarboardConfigOut:
    async with get_session() as session:
        cfg = await StarboardRepository(session).get_or_create_config(guild_id)
        cfg.channel_id = int(body.channel_id) if body.channel_id else None
        cfg.threshold = body.threshold
        cfg.star_emoji = body.star_emoji
        cfg.enabled = body.enabled
        cfg.self_star = body.self_star
        return _to_out(cfg)
