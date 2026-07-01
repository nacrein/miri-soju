"""Music config endpoints (per-guild MusicConfig row)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from dashboard.deps import require_guild
from dashboard.schemas import MusicConfigIn, MusicConfigOut
from src.database.session import get_session
from src.modules.music.repository import MusicRepository

router = APIRouter(prefix="/guilds/{guild_id}/music", tags=["music"])


def _to_out(cfg) -> MusicConfigOut:
    return MusicConfigOut(
        dj_role_id=str(cfg.dj_role_id) if cfg.dj_role_id else None,
        command_channel_id=str(cfg.command_channel_id) if cfg.command_channel_id else None,
        default_volume=cfg.default_volume,
    )


@router.get("", response_model=MusicConfigOut)
async def get_config(guild_id: int = Depends(require_guild)) -> MusicConfigOut:
    async with get_session() as session:
        cfg = await MusicRepository(session).get_or_create_config(guild_id)
        return _to_out(cfg)


@router.put("", response_model=MusicConfigOut)
async def update_config(
    body: MusicConfigIn, guild_id: int = Depends(require_guild)
) -> MusicConfigOut:
    async with get_session() as session:
        cfg = await MusicRepository(session).get_or_create_config(guild_id)
        cfg.dj_role_id = int(body.dj_role_id) if body.dj_role_id else None
        cfg.command_channel_id = (
            int(body.command_channel_id) if body.command_channel_id else None
        )
        cfg.default_volume = body.default_volume
        return _to_out(cfg)
