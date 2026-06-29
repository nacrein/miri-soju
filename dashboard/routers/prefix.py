"""Prefix config endpoints — the guild's command prefix, stored on GuildConfig.

Pattern (mirrors ``leveling.py``):
- Depend on ``require_guild`` so the path's guild id is authorized and returned.
- Open ``get_session()`` (it commits on success, rolls back on error).
- Go through the module's *existing* repository — never hand-roll SQL here.
- The prefix is a plain string (not a snowflake), so no int<->str conversion;
  ``None`` means "use the global default".
- Mutations return the fresh full config so the client refreshes in one round-trip.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from dashboard.deps import require_guild
from dashboard.schemas import PrefixIn, PrefixOut
from src.database.session import get_session
from src.modules.prefix.service import DEFAULT_PREFIX
from src.modules.serverlog.repository import GuildConfigRepository

router = APIRouter(prefix="/guilds/{guild_id}/prefix", tags=["prefix"])


@router.get("", response_model=PrefixOut)
async def get_prefix(guild_id: int = Depends(require_guild)) -> PrefixOut:
    async with get_session() as session:
        cfg = await GuildConfigRepository(session).get_or_create(guild_id)
        return PrefixOut(prefix=cfg.prefix or None, default=DEFAULT_PREFIX)


@router.put("", response_model=PrefixOut)
async def update_prefix(
    body: PrefixIn, guild_id: int = Depends(require_guild)
) -> PrefixOut:
    async with get_session() as session:
        cfg = await GuildConfigRepository(session).get_or_create(guild_id)
        cfg.prefix = body.prefix  # None resets to the global default
        return PrefixOut(prefix=cfg.prefix or None, default=DEFAULT_PREFIX)
