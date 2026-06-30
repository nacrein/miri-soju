"""VoiceMaster config endpoints (per-guild VoiceMasterConfig row).

Only the basics are dashboard-editable: the on/off flag and the join-to-create
voice channel. The control-panel message (panel_channel_id/panel_message_id) is
posted and tracked by the bot's own ``,setup`` flow, so the dashboard leaves it
untouched rather than write a panel pointer it can't actually create."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from dashboard.deps import require_guild
from dashboard.schemas import VoiceMasterConfigIn, VoiceMasterConfigOut
from src.database.session import get_session
from src.modules.voicemaster.repository import VoiceMasterRepository

router = APIRouter(prefix="/guilds/{guild_id}/voicemaster", tags=["voicemaster"])


def _to_out(cfg) -> VoiceMasterConfigOut:
    return VoiceMasterConfigOut(
        enabled=cfg.enabled,
        create_channel_id=str(cfg.create_channel_id) if cfg.create_channel_id else None,
    )


@router.get("", response_model=VoiceMasterConfigOut)
async def get_config(guild_id: int = Depends(require_guild)) -> VoiceMasterConfigOut:
    async with get_session() as session:
        cfg = await VoiceMasterRepository(session).get_or_create_config(guild_id)
        return _to_out(cfg)


@router.put("", response_model=VoiceMasterConfigOut)
async def update_config(
    body: VoiceMasterConfigIn, guild_id: int = Depends(require_guild)
) -> VoiceMasterConfigOut:
    async with get_session() as session:
        cfg = await VoiceMasterRepository(session).get_or_create_config(guild_id)
        cfg.enabled = body.enabled
        cfg.create_channel_id = (
            int(body.create_channel_id) if body.create_channel_id else None
        )
        return _to_out(cfg)
