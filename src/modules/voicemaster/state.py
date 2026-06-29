"""In-memory VoiceMaster timing state — no discord, no DB.

Two things live here so both the cog and the persistent view can reach them without
a circular import: the per-channel rename rate-limit (mirrors Discord's 2-per-10-min
name-edit bucket) and the per-user create-channel cooldown."""

from __future__ import annotations

import time
from collections import deque

from src.modules.voicemaster import config

_rename: dict[int, deque] = {}                 # channel_id -> recent rename monotonic times
_create: dict[tuple[int, int], float] = {}     # (guild_id, user_id) -> last create monotonic


def rename_allowed(channel_id: int) -> bool:
    """False once a channel has used its rename bucket (RENAME_MAX in the window)."""
    dq = _rename.get(channel_id)
    if dq is None:
        return True
    cutoff = time.monotonic() - config.RENAME_WINDOW_SECONDS
    while dq and dq[0] < cutoff:
        dq.popleft()
    return len(dq) < config.RENAME_MAX


def record_rename(channel_id: int) -> None:
    dq = _rename.setdefault(channel_id, deque(maxlen=config.RENAME_MAX))
    dq.append(time.monotonic())


def forget_channel(channel_id: int) -> None:
    """Drop a deleted channel's rename history."""
    _rename.pop(channel_id, None)


def on_create_cooldown(guild_id: int, user_id: int) -> bool:
    last = _create.get((guild_id, user_id))
    if last is None:
        return False
    if time.monotonic() - last >= config.CREATE_COOLDOWN_SECONDS:
        del _create[(guild_id, user_id)]  # expired; drop it so the dict stays small
        return False
    return True


def mark_create(guild_id: int, user_id: int) -> None:
    _create[(guild_id, user_id)] = time.monotonic()
