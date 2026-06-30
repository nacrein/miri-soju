"""Tests for the leveling XP curve and the message-XP award path.

The three curve functions must agree exactly: ``xp_to_advance(level)`` is the
per-level cost, ``total_xp_for_level`` its closed-form cumulative sum, and
``level_from_xp`` the inverse. A single off-by-one in any of them silently
corrupts every level boundary, so they're pinned here. ``award_message_xp`` is
covered DB-backed (the cooldown gate and the level-up return on crossing).
"""

from __future__ import annotations

from src.database.base import Base
from src.database.session import engine
from src.modules.leveling import config, service

# ── curve invariants (pure) ───────────────────────────────────────────────────

def test_total_xp_is_the_running_sum_of_xp_to_advance():
    # total_xp_for_level(n+1) - total_xp_for_level(n) must equal the cost of level n.
    for n in range(0, 30):
        step = config.total_xp_for_level(n + 1) - config.total_xp_for_level(n)
        assert step == config.xp_to_advance(n), n


def test_level_from_xp_inverts_total_xp_for_level_at_the_boundaries():
    for level in range(0, 30):
        assert config.level_from_xp(config.total_xp_for_level(level)) == level
        if level > 0:
            # One XP short of the boundary is still the previous level.
            assert config.level_from_xp(config.total_xp_for_level(level) - 1) == level - 1


def test_level_from_xp_floors_at_zero_and_handles_partial_progress():
    assert config.level_from_xp(0) == 0
    assert config.level_from_xp(-100) == 0
    assert config.level_from_xp(config.total_xp_for_level(1) - 1) == 0  # 99 XP → still level 0
    assert config.level_from_xp(config.total_xp_for_level(1)) == 1      # 100 XP → level 1


def test_level_from_xp_is_fast_and_correct_at_the_high_end():
    # The cog allows setlevel up to 1000; the inverse must still land exactly there.
    top = config.total_xp_for_level(1000)
    assert config.level_from_xp(top) == 1000
    assert config.level_from_xp(top - 1) == 999


# ── message-XP award (DB-backed) ──────────────────────────────────────────────

async def _schema() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def test_award_message_xp_is_gated_by_the_cooldown():
    await _schema()
    guild, user = 660001, 770001
    await service.set_enabled(guild, True)
    await service.set_rate(guild, 30)
    await service.set_cooldown(guild, 60)

    first = await service.award_message_xp(guild, user, channel_id=1)
    second = await service.award_message_xp(guild, user, channel_id=1)  # within cooldown

    assert first is None          # 30 XP < 100, no level-up
    assert second is None         # gated → no second award
    p = await service.get_progress(guild, user)
    assert p["xp"] == 30          # only the first message counted


async def test_award_message_xp_returns_new_level_on_crossing_a_boundary():
    await _schema()
    guild, user = 660002, 770002
    await service.set_enabled(guild, True)
    await service.set_rate(guild, 100)   # one message crosses level 0 → 1 (boundary = 100)
    await service.set_cooldown(guild, 0)  # no gate so we can step repeatedly

    level = await service.award_message_xp(guild, user, channel_id=1)
    assert level == 1
    p = await service.get_progress(guild, user)
    assert p["xp"] == 100
    assert p["level"] == 1


async def test_award_message_xp_no_levelup_when_staying_below_boundary():
    await _schema()
    guild, user = 660003, 770003
    await service.set_enabled(guild, True)
    await service.set_rate(guild, 40)
    await service.set_cooldown(guild, 0)

    assert await service.award_message_xp(guild, user, channel_id=1) is None  # 40
    assert await service.award_message_xp(guild, user, channel_id=1) is None  # 80, still level 0
    assert await service.award_message_xp(guild, user, channel_id=1) == 1     # 120 → level 1


async def test_voice_fractional_multiplier_accumulates_across_minutes():
    # Regression: int(VOICE_XP_PER_MINUTE * mult) once floored fractional rates to
    # 0/min; the gain must be computed over the whole minute span instead.
    await _schema()
    guild, user, channel = 660004, 770004, 1234
    await service.set_enabled(guild, True)
    await service.set_multiplier(guild, channel, 0.5)  # 10 * 0.5 = 5 XP/min
    await service.credit_voice([(guild, user, channel, 4)])
    p = await service.get_progress(guild, user)
    assert p["voice_minutes"] == 4
    assert p["xp"] == config.VOICE_XP_PER_MINUTE * 0.5 * 4  # 20, not 0
