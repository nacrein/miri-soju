"""Booster-role logic: cached config, persisted role records, and color parsing.

No discord here — the cog performs the actual create/edit/delete on the Discord
role; this module owns the database record and the pure helpers. Persisting
name/color/icon is precisely what lets a reboost reconstruct a deleted role
identically (see ``desired_state``)."""

from __future__ import annotations

import string

from src.core.cache import TTLCache
from src.core.errors import BotError
from src.database.models.boosterrole import BoosterRole
from src.database.session import get_session
from src.modules.boosterrole.repository import BoosterRoleRepository

_NO_CONFIG = object()
_config_cache: TTLCache = TTLCache(ttl_seconds=300)  # guild_id -> BoosterRoleConfig | _NO_CONFIG
_UNSET = object()


# ── pure helpers ───────────────────────────────────────────────────────────────

def parse_color(raw: str) -> int:
    """Parse ``#abc``, ``#aabbcc``, or bare hex into an int 0x000000–0xFFFFFF.

    Raises :class:`BotError` on malformed or out-of-range input."""
    s = raw.strip().lstrip("#").strip()
    if len(s) == 3 and all(c in string.hexdigits for c in s):
        s = "".join(c * 2 for c in s)  # #abc -> #aabbcc
    if len(s) != 6 or any(c not in string.hexdigits for c in s):
        raise BotError("Color must be a hex like `#5865f2`, `#abc`, or `5865f2`.")
    value = int(s, 16)
    if not 0 <= value <= 0xFFFFFF:  # six hex digits already bound this; explicit anyway
        raise BotError("Color is out of range (must be #000000-#ffffff).")
    return value


# ── config (cached read-through; setters invalidate) ───────────────────────────

async def get_config(guild_id: int):
    cached = _config_cache.get(guild_id)
    if cached is not None:
        return None if cached is _NO_CONFIG else cached
    async with get_session() as session:
        cfg = await BoosterRoleRepository(session).get_config(guild_id)
    _config_cache.set(guild_id, cfg if cfg is not None else _NO_CONFIG)
    return cfg


async def _set(guild_id: int, **fields) -> None:
    async with get_session() as session:
        cfg = await BoosterRoleRepository(session).get_or_create_config(guild_id)
        for key, value in fields.items():
            setattr(cfg, key, value)
    _config_cache.invalidate(guild_id)


async def set_enabled(guild_id: int, value: bool) -> None:
    await _set(guild_id, enabled=value)


async def set_hoist_above(guild_id: int, value: bool) -> None:
    await _set(guild_id, hoist_above=value)


async def set_anchor(guild_id: int, role_id: int | None) -> None:
    await _set(guild_id, anchor_role_id=role_id)


async def reset_config(guild_id: int) -> None:
    await _set(guild_id, enabled=False, hoist_above=True, anchor_role_id=None)


# ── role records ───────────────────────────────────────────────────────────────

async def get_booster_role(guild_id: int, user_id: int) -> BoosterRole | None:
    async with get_session() as session:
        return await BoosterRoleRepository(session).get_role(guild_id, user_id)


async def create_role(
    guild_id: int, user_id: int, role_id: int, name: str, color: int, icon: str | None = None
) -> None:
    """Persist (or replace) the member's booster-role record."""
    async with get_session() as session:
        repo = BoosterRoleRepository(session)
        await repo.upsert_role(guild_id, user_id, role_id, name, color, icon)


async def update_role(
    guild_id: int, user_id: int, *, role_id=_UNSET, name=_UNSET, color=_UNSET, icon=_UNSET
) -> bool:
    """Update only the provided fields of the member's record. Returns whether it existed."""
    fields: dict = {}
    if role_id is not _UNSET:
        fields["role_id"] = role_id
    if name is not _UNSET:
        fields["name"] = name
    if color is not _UNSET:
        fields["color"] = color
    if icon is not _UNSET:
        fields["icon"] = icon
    if not fields:
        return False
    async with get_session() as session:
        return await BoosterRoleRepository(session).update_role_fields(guild_id, user_id, fields)


async def delete_role(guild_id: int, user_id: int) -> bool:
    async with get_session() as session:
        return await BoosterRoleRepository(session).delete_role(guild_id, user_id)


async def clear_by_role(guild_id: int, role_id: int) -> bool:
    """Drop the record whose stored role_id matches (an admin deleted the role)."""
    async with get_session() as session:
        return await BoosterRoleRepository(session).clear_by_role(guild_id, role_id)


async def list_roles(guild_id: int) -> list[BoosterRole]:
    async with get_session() as session:
        return await BoosterRoleRepository(session).list_roles(guild_id)


async def list_all() -> list[BoosterRole]:
    async with get_session() as session:
        return await BoosterRoleRepository(session).list_all()


async def desired_state(guild_id: int, user_id: int) -> tuple[str, int, str | None] | None:
    """The stored (name, color, icon) for faithful re-creation, or None if no record."""
    record = await get_booster_role(guild_id, user_id)
    if record is None:
        return None
    return (record.name, record.color, record.icon)
