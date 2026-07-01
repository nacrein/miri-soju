"""Welcome/goodbye config endpoints (per-guild WelcomeConfig row).

Pattern copied from ``serverlog.py``: GET/PUT the single config row through the
module's own repository, converting snowflakes int<->str at the boundary."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from dashboard.deps import require_guild
from dashboard.schemas import WelcomeConfigIn, WelcomeConfigOut
from src.database.session import get_session
from src.modules.welcome.repository import WelcomeConfigRepository

router = APIRouter(prefix="/guilds/{guild_id}/welcome", tags=["welcome"])


def _to_out(cfg) -> WelcomeConfigOut:
    return WelcomeConfigOut(
        welcome_channel_id=str(cfg.welcome_channel_id) if cfg.welcome_channel_id else None,
        welcome_message=cfg.welcome_message,
        welcome_enabled=cfg.welcome_enabled,
        goodbye_channel_id=str(cfg.goodbye_channel_id) if cfg.goodbye_channel_id else None,
        goodbye_message=cfg.goodbye_message,
        goodbye_enabled=cfg.goodbye_enabled,
    )


@router.get("", response_model=WelcomeConfigOut)
async def get_config(guild_id: int = Depends(require_guild)) -> WelcomeConfigOut:
    async with get_session() as session:
        cfg = await WelcomeConfigRepository(session).get_or_create(guild_id)
        return _to_out(cfg)


@router.put("", response_model=WelcomeConfigOut)
async def update_config(
    body: WelcomeConfigIn, guild_id: int = Depends(require_guild)
) -> WelcomeConfigOut:
    async with get_session() as session:
        cfg = await WelcomeConfigRepository(session).get_or_create(guild_id)
        cfg.welcome_channel_id = int(body.welcome_channel_id) if body.welcome_channel_id else None
        cfg.welcome_message = body.welcome_message
        cfg.welcome_enabled = body.welcome_enabled
        cfg.goodbye_channel_id = int(body.goodbye_channel_id) if body.goodbye_channel_id else None
        cfg.goodbye_message = body.goodbye_message
        cfg.goodbye_enabled = body.goodbye_enabled
        return _to_out(cfg)
