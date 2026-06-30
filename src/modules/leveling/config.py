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
    """Highest level fully paid for by `xp`.

    ``total_xp_for_level`` is monotonically increasing, so binary-search for the
    highest level whose cumulative cost is still affordable — O(log level) instead
    of an O(level) linear scan (the old loop did ~1000 cubic evals at level 1000)."""
    if xp <= 0:
        return 0
    # Find an upper bound by doubling, then bisect on [lo, hi].
    hi = 1
    while total_xp_for_level(hi) <= xp:
        hi *= 2
    lo = hi // 2  # total_xp_for_level(lo) <= xp < total_xp_for_level(hi)
    while lo + 1 < hi:
        mid = (lo + hi) // 2
        if total_xp_for_level(mid) <= xp:
            lo = mid
        else:
            hi = mid
    return lo
