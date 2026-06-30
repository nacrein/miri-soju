"""Welcome/goodbye config logic. No discord here — the cog renders and sends.

Config is read on every join/leave but changes rarely, so it's cached read-through
with a TTL (mirroring serverlog); writes invalidate the cache for instant effect."""

from __future__ import annotations

from src.core.cache import TTLCache
from src.database.models.welcome import WelcomeConfig
from src.database.session import get_session
from src.modules.welcome.repository import WelcomeConfigRepository

DEFAULT_WELCOME = "Welcome {user} to **{server}**! You're member #{count}."
DEFAULT_GOODBYE = "**{name}** has left {server}."

# kind -> (channel column, message column, enabled column)
_FIELDS = {
    "welcome": ("welcome_channel_id", "welcome_message", "welcome_enabled"),
    "goodbye": ("goodbye_channel_id", "goodbye_message", "goodbye_enabled"),
}
_DEFAULTS = {"welcome": DEFAULT_WELCOME, "goodbye": DEFAULT_GOODBYE}

_NO_CONFIG = object()
_config_cache: TTLCache = TTLCache(ttl_seconds=300)


async def _load(guild_id: int) -> WelcomeConfig | None:
    """Read-through: cache first, DB on miss, negative-caching a missing row."""
    cached = _config_cache.get(guild_id)
    if cached is not None:
        return None if cached is _NO_CONFIG else cached
    async with get_session() as session:
        config = await WelcomeConfigRepository(session).get(guild_id)
    _config_cache.set(guild_id, config if config is not None else _NO_CONFIG)
    return config


async def _mutate(guild_id: int, **values) -> None:
    async with get_session() as session:
        config = await WelcomeConfigRepository(session).get_or_create(guild_id)
        for field, value in values.items():
            setattr(config, field, value)
    _config_cache.invalidate(guild_id)


async def set_channel(guild_id: int, kind: str, channel_id: int) -> None:
    """Point a kind at a channel and enable it in one write."""
    ch_field, _msg, en_field = _FIELDS[kind]
    await _mutate(guild_id, **{ch_field: channel_id, en_field: True})


async def set_message(guild_id: int, kind: str, message: str) -> None:
    _ch, msg_field, _en = _FIELDS[kind]
    await _mutate(guild_id, **{msg_field: message})


async def set_enabled(guild_id: int, kind: str, value: bool) -> None:
    _ch, _msg, en_field = _FIELDS[kind]
    await _mutate(guild_id, **{en_field: value})


async def resolve(guild_id: int, kind: str) -> tuple[int, str] | None:
    """The (channel_id, template) to use for this kind, or None if it's off/unset."""
    config = await _load(guild_id)
    if config is None:
        return None
    ch_field, msg_field, en_field = _FIELDS[kind]
    if not getattr(config, en_field) or getattr(config, ch_field) is None:
        return None
    return getattr(config, ch_field), getattr(config, msg_field) or _DEFAULTS[kind]


async def get_summary(guild_id: int) -> dict:
    """Both kinds' settings for the status command and the setup panel."""
    config = await _load(guild_id)
    out = {}
    for kind in _FIELDS:
        ch_field, msg_field, en_field = _FIELDS[kind]
        out[kind] = {
            "enabled": bool(config and getattr(config, en_field)),
            "channel_id": getattr(config, ch_field) if config else None,
            "message": (getattr(config, msg_field) if config else None) or _DEFAULTS[kind],
        }
    return out
