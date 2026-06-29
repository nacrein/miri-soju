"""Moderation config endpoints — follows the leveling router shape.

Pattern (see ``dashboard/routers/leveling.py`` for the canonical version):
- Depend on ``require_guild`` so the path's guild id is authorized and returned.
- Open ``get_session()`` (it commits on success, rolls back on error).
- Go through the module's *existing* repository — never hand-roll SQL here.
- Convert snowflakes int<->str at the boundary (DB stores int; the wire uses str).
- Mutations return the fresh full config so the client refreshes in one round-trip.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from dashboard.deps import require_guild
from dashboard.schemas import ModerationConfigIn, ModerationConfigOut
from src.database.models.jail import ModerationConfig
from src.database.session import get_session
from src.modules.moderation.repository import ModerationRepository

router = APIRouter(prefix="/guilds/{guild_id}/moderation", tags=["moderation"])


@router.get("", response_model=ModerationConfigOut)
async def get_config(guild_id: int = Depends(require_guild)) -> ModerationConfigOut:
    async with get_session() as session:
        repo = ModerationRepository(session)
        jail = await repo.get_jail_role(guild_id)
        return ModerationConfigOut(jail_role_id=str(jail) if jail else None)


@router.put("", response_model=ModerationConfigOut)
async def update_config(
    body: ModerationConfigIn, guild_id: int = Depends(require_guild)
) -> ModerationConfigOut:
    async with get_session() as session:
        repo = ModerationRepository(session)
        if body.jail_role_id is not None:
            await repo.set_jail_role(guild_id, int(body.jail_role_id))
        else:
            cfg = await session.get(ModerationConfig, guild_id)
            if cfg is None:
                session.add(ModerationConfig(guild_id=guild_id))
            else:
                cfg.jail_role_id = None
        jail = await repo.get_jail_role(guild_id)
        return ModerationConfigOut(jail_role_id=str(jail) if jail else None)
