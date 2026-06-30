"""Music config + pure helpers. No discord, no wavelink.

This module is the *documented exception* to the cog -> service -> repository pattern:
playback and queue state live in ``wavelink.Player`` (backed by the node), so the cog
holds that state directly. The service owns only what genuinely fits the pattern — the
per-guild config (read through a TTL cache) and small pure, testable helpers. The one
import that touches the commands layer is ``BotError``, the app's user-facing error type
that ``parse_timestamp`` is specified to raise; the service still never touches discord
or wavelink objects.
"""

from __future__ import annotations

import math

from src.core.cache import TTLCache
from src.core.errors import BotError
from src.database.session import get_session
from src.modules.music import config
from src.modules.music.repository import MusicRepository

_NO_CONFIG = object()
_config_cache: TTLCache = TTLCache(ttl_seconds=300)


# ── config (read-through cache; setters invalidate) ──────────────────────────────

async def get_config(guild_id: int):
    cached = _config_cache.get(guild_id)
    if cached is not None:
        return None if cached is _NO_CONFIG else cached
    async with get_session() as session:
        cfg = await MusicRepository(session).get_config(guild_id)
    _config_cache.set(guild_id, cfg if cfg is not None else _NO_CONFIG)
    return cfg


async def set_dj_role(guild_id: int, role_id: int | None) -> None:
    async with get_session() as session:
        (await MusicRepository(session).get_or_create_config(guild_id)).dj_role_id = role_id
    _config_cache.invalidate(guild_id)


async def set_command_channel(guild_id: int, channel_id: int | None) -> None:
    async with get_session() as session:
        cfg = await MusicRepository(session).get_or_create_config(guild_id)
        cfg.command_channel_id = channel_id
    _config_cache.invalidate(guild_id)


async def set_default_volume(guild_id: int, volume: int) -> None:
    async with get_session() as session:
        (await MusicRepository(session).get_or_create_config(guild_id)).default_volume = volume
    _config_cache.invalidate(guild_id)


# ── pure helpers (no I/O, no discord/wavelink) ───────────────────────────────────

def parse_timestamp(text: str) -> int:
    """Parse ``ss``, ``m:ss``, or ``h:mm:ss`` into milliseconds.

    Raises :class:`BotError` on anything that isn't 1-3 colon-separated integers."""
    parts = text.strip().split(":")
    if not 1 <= len(parts) <= 3 or not all(p.isdigit() for p in parts):
        raise BotError("Give a timestamp like `90`, `1:30`, or `1:02:03`.")
    seconds = 0
    for part in parts:
        seconds = seconds * 60 + int(part)
    return seconds * 1000


def format_duration(ms: int | None) -> str:
    """Milliseconds -> ``m:ss`` or ``h:mm:ss``. A stream (0 / None) renders as ``LIVE``."""
    if not ms or ms <= 0:
        return "LIVE"
    total = ms // 1000
    hours, rem = divmod(total, 3600)
    minutes, seconds = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def needs_votes(listener_count: int) -> int:
    """Votes required to force a skip: a majority of non-bot listeners, at least 1."""
    effective = max(listener_count, 1)
    return max(1, math.ceil(effective * config.SKIP_VOTE_RATIO))
