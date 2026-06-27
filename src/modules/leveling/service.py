"""Leveling logic: XP awards, the cached config/multiplier reads, and queries."""

from __future__ import annotations

import time
from datetime import datetime, timezone

from src.core.cache import TTLCache
from src.database.models.level import LevelConfig
from src.database.session import get_session
from src.modules.leveling import config
from src.modules.leveling.repository import LevelingRepository

_NO_CONFIG = object()
_config_cache: TTLCache = TTLCache(ttl_seconds=300)        # guild_id -> LevelConfig | _NO_CONFIG
_mult_cache: TTLCache = TTLCache(ttl_seconds=300)          # guild_id -> {channel_id: multiplier}
_msg_cooldown: dict[tuple[int, int], float] = {}           # in-memory message-XP gate


def _now() -> datetime:
    return datetime.now(timezone.utc)


def render_message(template: str, member, level: int, guild) -> str:
    return (template
            .replace("{user.name}", member.display_name)
            .replace("{user}", member.mention)
            .replace("{level}", str(level))
            .replace("{server}", guild.name))


async def get_config(guild_id: int):
    cached = _config_cache.get(guild_id)
    if cached is not None:
        return None if cached is _NO_CONFIG else cached
    async with get_session() as session:
        cfg = await LevelingRepository(session).get_config(guild_id)
    _config_cache.set(guild_id, cfg if cfg is not None else _NO_CONFIG)
    return cfg


async def _multipliers(guild_id: int) -> dict[int, float]:
    cached = _mult_cache.get(guild_id)
    if cached is not None:
        return cached
    async with get_session() as session:
        rows = await LevelingRepository(session).list_multipliers(guild_id)
    table = {cid: m for cid, m in rows}
    _mult_cache.set(guild_id, table)
    return table


# ── XP awards ───────────────────────────────────────────────────────────────

async def award_message_xp(guild_id: int, user_id: int, channel_id: int) -> int | None:
    """Award message XP. Returns the new level on a level-up, else None."""
    cfg = await get_config(guild_id)
    if cfg is None or not cfg.enabled:
        return None
    key = (guild_id, user_id)
    mono = time.monotonic()
    last = _msg_cooldown.get(key)
    if last is not None and mono - last < cfg.message_cooldown:
        return None
    mult = (await _multipliers(guild_id)).get(channel_id, 1.0)
    gain = int(cfg.xp_per_message * mult)
    if gain <= 0:
        return None
    _msg_cooldown[key] = mono
    async with get_session() as session:
        repo = LevelingRepository(session)
        member = await repo.get_or_create_member(guild_id, user_id)
        old = config.level_from_xp(member.xp)
        member.xp += gain
        member.last_message_at = _now()
        new = config.level_from_xp(member.xp)
    return new if new > old else None


async def award_voice_xp(guild_id: int, user_id: int, channel_id: int) -> int | None:
    """Award one minute of voice XP. Returns the new level on a level-up, else None."""
    cfg = await get_config(guild_id)
    if cfg is None or not cfg.enabled:
        return None
    mult = (await _multipliers(guild_id)).get(channel_id, 1.0)
    gain = int(config.VOICE_XP_PER_MINUTE * mult)
    async with get_session() as session:
        repo = LevelingRepository(session)
        member = await repo.get_or_create_member(guild_id, user_id)
        old = config.level_from_xp(member.xp)
        member.xp += gain
        member.voice_minutes += 1
        new = config.level_from_xp(member.xp)
    return new if new > old else None


# ── member queries ──────────────────────────────────────────────────────────

async def get_progress(guild_id: int, user_id: int) -> dict:
    async with get_session() as session:
        repo = LevelingRepository(session)
        member = await repo.get_member(guild_id, user_id)
        xp = member.xp if member else 0
        voice = member.voice_minutes if member else 0
        rank = await repo.rank_by_xp(guild_id, xp) if member else None
    level = config.level_from_xp(xp)
    floor = config.total_xp_for_level(level)
    ceil = config.total_xp_for_level(level + 1)
    return {"xp": xp, "level": level, "into": xp - floor, "needed": ceil - floor,
            "voice_minutes": voice, "rank": rank}


async def set_level(guild_id: int, user_id: int, level: int) -> None:
    target = config.total_xp_for_level(level)
    async with get_session() as session:
        member = await LevelingRepository(session).get_or_create_member(guild_id, user_id)
        member.xp = target


async def reset_member(guild_id: int, user_id: int) -> bool:
    async with get_session() as session:
        return await LevelingRepository(session).reset_member(guild_id, user_id)


async def reset_all(guild_id: int) -> int:
    async with get_session() as session:
        return await LevelingRepository(session).reset_all(guild_id)


# ── config setters (invalidate the cache) ──────────────────────────────────

async def set_enabled(guild_id: int, value: bool) -> None:
    async with get_session() as session:
        (await LevelingRepository(session).get_or_create_config(guild_id)).enabled = value
    _config_cache.invalidate(guild_id)


async def set_rate(guild_id: int, amount: int) -> None:
    async with get_session() as session:
        (await LevelingRepository(session).get_or_create_config(guild_id)).xp_per_message = amount
    _config_cache.invalidate(guild_id)


async def set_cooldown(guild_id: int, seconds: int) -> None:
    async with get_session() as session:
        (await LevelingRepository(session).get_or_create_config(guild_id)).message_cooldown = seconds
    _config_cache.invalidate(guild_id)


async def set_channel(guild_id: int, mode: str, channel_id: int | None) -> None:
    async with get_session() as session:
        cfg = await LevelingRepository(session).get_or_create_config(guild_id)
        cfg.announce_mode = mode
        cfg.announce_channel_id = channel_id
    _config_cache.invalidate(guild_id)


async def set_message(guild_id: int, text: str) -> None:
    async with get_session() as session:
        (await LevelingRepository(session).get_or_create_config(guild_id)).level_up_message = text
    _config_cache.invalidate(guild_id)


# ── rewards and multipliers ─────────────────────────────────────────────────

async def add_reward(guild_id: int, level: int, role_id: int) -> None:
    async with get_session() as session:
        await LevelingRepository(session).add_reward(guild_id, level, role_id)


async def remove_reward(guild_id: int, level: int) -> bool:
    async with get_session() as session:
        return await LevelingRepository(session).remove_reward(guild_id, level)


async def list_rewards(guild_id: int) -> list[tuple[int, int]]:
    async with get_session() as session:
        return await LevelingRepository(session).list_rewards(guild_id)


async def rewards_up_to(guild_id: int, level: int) -> list[tuple[int, int]]:
    async with get_session() as session:
        return await LevelingRepository(session).rewards_up_to(guild_id, level)


async def set_multiplier(guild_id: int, channel_id: int, multiplier: float) -> None:
    async with get_session() as session:
        await LevelingRepository(session).set_multiplier(guild_id, channel_id, multiplier)
    _mult_cache.invalidate(guild_id)


async def remove_multiplier(guild_id: int, channel_id: int) -> bool:
    async with get_session() as session:
        removed = await LevelingRepository(session).remove_multiplier(guild_id, channel_id)
    _mult_cache.invalidate(guild_id)
    return removed


async def list_multipliers(guild_id: int) -> list[tuple[int, float]]:
    async with get_session() as session:
        return await LevelingRepository(session).list_multipliers(guild_id)


# ── leaderboard feeds (called by the leaderboard module) ───────────────────

async def leaderboard_level(guild_id: int, limit: int = 10) -> list[tuple[int, int]]:
    async with get_session() as session:
        rows = await LevelingRepository(session).top_by_xp(guild_id, limit)
    return [(uid, config.level_from_xp(xp)) for uid, xp in rows]


async def leaderboard_voice(guild_id: int, limit: int = 10) -> list[tuple[int, str]]:
    async with get_session() as session:
        rows = await LevelingRepository(session).top_by_voice(guild_id, limit)
    return [(uid, f"{mins // 60}h {mins % 60}m") for uid, mins in rows]
