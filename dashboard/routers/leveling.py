"""Leveling config endpoints — the reference shape every module router follows.

Pattern (copy this for other modules):
- Depend on ``require_guild`` so the path's guild id is authorized and returned.
- Open ``get_session()`` (it commits on success, rolls back on error).
- Go through the module's *existing* repository — never hand-roll SQL here.
- Convert snowflakes int<->str at the boundary (DB stores int; the wire uses str).
- Mutations return the fresh full config so the client refreshes in one round-trip.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from dashboard.deps import require_guild
from dashboard.schemas import (
    ChannelMultiplierIn,
    ChannelMultiplierOut,
    LevelingConfigIn,
    LevelingConfigOut,
    LevelRewardIn,
    LevelRewardOut,
)
from src.database.session import get_session
from src.modules.leveling.repository import LevelingRepository

router = APIRouter(prefix="/guilds/{guild_id}/leveling", tags=["leveling"])


async def _load(session, guild_id: int) -> LevelingConfigOut:
    repo = LevelingRepository(session)
    cfg = await repo.get_or_create_config(guild_id)
    rewards = await repo.list_rewards(guild_id)
    mults = await repo.list_multipliers(guild_id)
    return LevelingConfigOut(
        enabled=cfg.enabled,
        xp_per_message=cfg.xp_per_message,
        message_cooldown=cfg.message_cooldown,
        announce_mode=cfg.announce_mode,
        announce_channel_id=str(cfg.announce_channel_id) if cfg.announce_channel_id else None,
        level_up_message=cfg.level_up_message,
        rewards=[LevelRewardOut(level=lvl, role_id=str(rid)) for lvl, rid in rewards],
        multipliers=[
            ChannelMultiplierOut(channel_id=str(cid), multiplier=m) for cid, m in mults
        ],
    )


@router.get("", response_model=LevelingConfigOut)
async def get_config(guild_id: int = Depends(require_guild)) -> LevelingConfigOut:
    async with get_session() as session:
        return await _load(session, guild_id)


@router.put("", response_model=LevelingConfigOut)
async def update_config(
    body: LevelingConfigIn, guild_id: int = Depends(require_guild)
) -> LevelingConfigOut:
    async with get_session() as session:
        repo = LevelingRepository(session)
        cfg = await repo.get_or_create_config(guild_id)
        cfg.enabled = body.enabled
        cfg.xp_per_message = body.xp_per_message
        cfg.message_cooldown = body.message_cooldown
        cfg.announce_mode = body.announce_mode
        cfg.announce_channel_id = (
            int(body.announce_channel_id) if body.announce_channel_id else None
        )
        cfg.level_up_message = body.level_up_message
        return await _load(session, guild_id)


@router.post("/rewards", response_model=LevelingConfigOut)
async def add_reward(
    body: LevelRewardIn, guild_id: int = Depends(require_guild)
) -> LevelingConfigOut:
    async with get_session() as session:
        repo = LevelingRepository(session)
        await repo.add_reward(guild_id, body.level, int(body.role_id))
        return await _load(session, guild_id)


@router.delete("/rewards/{level}", response_model=LevelingConfigOut)
async def remove_reward(
    level: int, guild_id: int = Depends(require_guild)
) -> LevelingConfigOut:
    async with get_session() as session:
        repo = LevelingRepository(session)
        await repo.remove_reward(guild_id, level)
        return await _load(session, guild_id)


@router.post("/multipliers", response_model=LevelingConfigOut)
async def set_multiplier(
    body: ChannelMultiplierIn, guild_id: int = Depends(require_guild)
) -> LevelingConfigOut:
    async with get_session() as session:
        repo = LevelingRepository(session)
        await repo.set_multiplier(guild_id, int(body.channel_id), body.multiplier)
        return await _load(session, guild_id)


@router.delete("/multipliers/{channel_id}", response_model=LevelingConfigOut)
async def remove_multiplier(
    channel_id: int, guild_id: int = Depends(require_guild)
) -> LevelingConfigOut:
    async with get_session() as session:
        repo = LevelingRepository(session)
        await repo.remove_multiplier(guild_id, channel_id)
        return await _load(session, guild_id)
