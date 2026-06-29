"""Leveling tuning: XP rates, the level curve, and the default message."""

from __future__ import annotations

XP_PER_MESSAGE = 20            # default; per-guild adjustable via ,levels rate
MESSAGE_COOLDOWN = 60          # default seconds between XP-earning messages
VOICE_XP_PER_MINUTE = 10       # XP per eligible voice minute (code-tunable)
DEFAULT_LEVEL_MESSAGE = "{user} reached level **{level}**!"

# Per-guild adjustable ranges, enforced by both ,levels and the ,setup levels panel.
RATE_MIN, RATE_MAX = 1, 1000
COOLDOWN_MIN, COOLDOWN_MAX = 0, 3600  # seconds
MESSAGE_MAX = 500                     # level-up template length cap


def xp_to_advance(level: int) -> int:
    """XP to go from `level` to `level + 1`."""
    return 5 * level * level + 50 * level + 100


def total_xp_for_level(level: int) -> int:
    """Cumulative XP needed to reach `level`."""
    if level <= 0:
        return 0
    n = level - 1
    return 5 * (n * (n + 1) * (2 * n + 1) // 6) + 25 * (level - 1) * level + 100 * level


def level_from_xp(xp: int) -> int:
    """Highest level fully paid for by `xp`."""
    level = 0
    while total_xp_for_level(level + 1) <= xp:
        level += 1
    return level
