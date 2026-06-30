"""VoiceMaster logic: cached config and the tracked-channel records.

No discord here — the cog spawns, moves, edits, and deletes the actual voice
channels; this module owns the config and the database records only."""

from __future__ import annotations

from src.core.cache import TTLCache
from src.database.models.voicemaster import VoiceMasterChannel
from src.database.session import get_session
from src.modules.voicemaster.repository import VoiceMasterRepository

_NO_CONFIG = object()
_config_cache: TTLCache = TTLCache(ttl_seconds=300)  # guild_id -> VoiceMasterConfig | _NO_CONFIG


# ── config (cached read-through; setters invalidate) ───────────────────────────

async def get_config(guild_id: int):
    cached = _config_cache.get(guild_id)
    if cached is not None:
        return None if cached is _NO_CONFIG else cached
    async with get_session() as session:
        cfg = await VoiceMasterRepository(session).get_config(guild_id)
    _config_cache.set(guild_id, cfg if cfg is not None else _NO_CONFIG)
    return cfg


async def _set(guild_id: int, **fields) -> None:
    async with get_session() as session:
        cfg = await VoiceMasterRepository(session).get_or_create_config(guild_id)
        for key, value in fields.items():
            setattr(cfg, key, value)
    _config_cache.invalidate(guild_id)


async def set_enabled(guild_id: int, value: bool) -> None:
    await _set(guild_id, enabled=value)


async def set_create_channel(guild_id: int, channel_id: int | None) -> None:
    await _set(guild_id, create_channel_id=channel_id)


async def set_panel_message(guild_id: int, panel_channel_id: int, panel_message_id: int) -> None:
    await _set(guild_id, panel_channel_id=panel_channel_id, panel_message_id=panel_message_id)


async def reset_config(guild_id: int) -> None:
    await _set(
        guild_id, enabled=False, create_channel_id=None,
        panel_channel_id=None, panel_message_id=None,
    )


# ── tracked channels ───────────────────────────────────────────────────────────

async def create_channel(guild_id: int, owner_id: int, channel_id: int) -> None:
    async with get_session() as session:
        await VoiceMasterRepository(session).add_channel(guild_id, owner_id, channel_id)


async def delete_channel(guild_id: int, channel_id: int) -> bool:
    async with get_session() as session:
        return await VoiceMasterRepository(session).delete_channel(guild_id, channel_id)


async def get_channel_by_id(guild_id: int, channel_id: int) -> VoiceMasterChannel | None:
    async with get_session() as session:
        return await VoiceMasterRepository(session).get_by_channel(guild_id, channel_id)


async def transfer_ownership(guild_id: int, channel_id: int, new_owner_id: int) -> bool:
    async with get_session() as session:
        return await VoiceMasterRepository(session).set_owner(guild_id, channel_id, new_owner_id)


async def list_tracked(guild_id: int) -> list[VoiceMasterChannel]:
    async with get_session() as session:
        return await VoiceMasterRepository(session).list_tracked(guild_id)
