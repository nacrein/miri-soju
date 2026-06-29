"""Serverlog config endpoints — settings stored on the shared ``GuildConfig`` row.

Pattern (copied from ``leveling.py``):
- Depend on ``require_guild`` so the path's guild id is authorized and returned.
- Open ``get_session()`` (it commits on success, rolls back on error).
- Go through the module's *existing* repository — never hand-roll SQL here.
- Convert snowflakes int<->str at the boundary (DB stores int; the wire uses str).
- Mutations return the fresh full config so the client refreshes in one round-trip.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from dashboard.deps import require_guild
from dashboard.schemas import ServerlogConfigIn, ServerlogConfigOut
from src.database.session import get_session
from src.modules.serverlog.repository import GuildConfigRepository

router = APIRouter(prefix="/guilds/{guild_id}/serverlog", tags=["serverlog"])


def _to_out(cfg) -> ServerlogConfigOut:
    return ServerlogConfigOut(
        log_channel_id=str(cfg.log_channel_id) if cfg.log_channel_id else None,
        log_joins=cfg.log_joins,
        log_leaves=cfg.log_leaves,
        log_message_delete=cfg.log_message_delete,
        log_message_edit=cfg.log_message_edit,
        log_mod_actions=cfg.log_mod_actions,
    )


@router.get("", response_model=ServerlogConfigOut)
async def get_config(guild_id: int = Depends(require_guild)) -> ServerlogConfigOut:
    async with get_session() as session:
        cfg = await GuildConfigRepository(session).get_or_create(guild_id)
        return _to_out(cfg)


@router.put("", response_model=ServerlogConfigOut)
async def update_config(
    body: ServerlogConfigIn, guild_id: int = Depends(require_guild)
) -> ServerlogConfigOut:
    async with get_session() as session:
        cfg = await GuildConfigRepository(session).get_or_create(guild_id)
        cfg.log_channel_id = int(body.log_channel_id) if body.log_channel_id else None
        cfg.log_joins = body.log_joins
        cfg.log_leaves = body.log_leaves
        cfg.log_message_delete = body.log_message_delete
        cfg.log_message_edit = body.log_message_edit
        cfg.log_mod_actions = body.log_mod_actions
        return _to_out(cfg)
