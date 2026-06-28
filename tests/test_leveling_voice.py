"""Tests for global, event-driven voice-time tracking.

Three layers, each isolated:
* ``VoiceTracker`` — pure interval bookkeeping (no Discord/DB/clock; ``now`` is fed in).
* ``Leveling._eligible`` — the per-member eligibility gate (fakes, no Discord).
* ``service.credit_voice`` — the batched DB write (hits the test SQLite DB).
"""

from __future__ import annotations

from types import SimpleNamespace

from src.database.base import Base
from src.database.session import engine
from src.modules.leveling import config, service
from src.modules.leveling.cog import Leveling
from src.modules.leveling.voice import VoiceTracker


# ── VoiceTracker: pure interval accrual ───────────────────────────────────────

def test_continuous_time_banks_whole_minutes_and_carries_the_rest():
    t = VoiceTracker()
    t.observe((1, 2), 100, True, 0.0)
    t.checkpoint(130.0)                       # 130s eligible → 2 min, 10s carried
    assert t.drain() == [(1, 2, 100, 2)]
    t.checkpoint(180.0)                       # +50s → 10+50 = 60s → 1 min
    assert t.drain() == [(1, 2, 100, 1)]


def test_intervals_combine_across_a_mute_or_deafen_gap():
    t = VoiceTracker()
    key = (1, 2)
    t.observe(key, 100, True, 0.0)            # eligible
    t.observe(key, 100, False, 40.0)          # muted after 40s eligible (gap starts)
    t.observe(key, 100, True, 50.0)           # unmuted (10s gap not counted)
    t.observe(key, 100, False, 70.0)          # muted after +20s → 40+20 = 60s → 1 min
    assert t.drain() == [(1, 2, 100, 1)]


def test_leave_keeps_whole_minutes_but_drops_the_remainder():
    t = VoiceTracker()
    key = (1, 2)
    t.observe(key, 100, True, 0.0)
    t.leave(key, 90.0)                        # 90s → 1 min credited, 30s discarded
    assert t.drain() == [(1, 2, 100, 1)]
    t.checkpoint(200.0)
    assert t.drain() == []                    # nothing lingers after leaving


def test_minutes_are_tracked_per_channel():
    t = VoiceTracker()
    key = (1, 2)
    t.observe(key, 100, True, 0.0)
    t.observe(key, 200, True, 60.0)           # moved to channel 200 after 60s in 100
    t.checkpoint(120.0)                        # +60s in 200
    assert dict(((g, u, c), m) for g, u, c, m in t.drain()) == {(1, 2, 100): 1, (1, 2, 200): 1}


def test_drain_clears_and_restore_requeues():
    t = VoiceTracker()
    t.observe((1, 2), 100, True, 0.0)
    t.checkpoint(60.0)
    batch = t.drain()
    assert batch == [(1, 2, 100, 1)]
    assert t.drain() == []                    # drain emptied the buffer
    t.restore(batch)                          # a failed write puts it back
    assert t.drain() == [(1, 2, 100, 1)]


# ── eligibility gate ──────────────────────────────────────────────────────────

def _member(humans: int = 2, *, bot=False, afk=False,
            self_mute=False, mute=False, self_deaf=False, deaf=False):
    me = SimpleNamespace(bot=bot)
    others = [SimpleNamespace(bot=False) for _ in range(max(0, humans - 1))]
    channel = SimpleNamespace(members=[me, *others])
    guild = SimpleNamespace(afk_channel=(channel if afk else SimpleNamespace(members=[])))
    me.guild = guild
    me.voice = SimpleNamespace(
        channel=channel, self_mute=self_mute, mute=mute, self_deaf=self_deaf, deaf=deaf
    )
    return me


def test_eligibility_gate():
    cog = Leveling.__new__(Leveling)  # bypass __init__; _eligible needs no state
    assert cog._eligible(_member(humans=2)) is True
    assert cog._eligible(_member(humans=1)) is False        # alone
    assert cog._eligible(_member(humans=2, self_mute=True)) is False
    assert cog._eligible(_member(humans=2, self_deaf=True)) is False  # deafened doesn't count
    assert cog._eligible(_member(humans=2, deaf=True)) is False
    assert cog._eligible(_member(humans=2, afk=True)) is False        # parked in AFK
    assert cog._eligible(_member(humans=2, bot=True)) is False


# ── batched DB credit ─────────────────────────────────────────────────────────

async def _schema() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def test_credit_voice_counts_minutes_even_when_leveling_is_disabled():
    await _schema()
    guild, user = 880001, 990001  # never enabled leveling
    await service.credit_voice([(guild, user, 1, 5)])
    p = await service.get_progress(guild, user)
    assert p["voice_minutes"] == 5  # voice time is global → always counted
    assert p["xp"] == 0             # but no XP where leveling is off


async def test_credit_voice_awards_xp_where_enabled():
    await _schema()
    guild, user = 880002, 990002
    await service.set_enabled(guild, True)
    await service.credit_voice([(guild, user, 1, 3)])
    p = await service.get_progress(guild, user)
    assert p["voice_minutes"] == 3
    assert p["xp"] == config.VOICE_XP_PER_MINUTE * 3


async def test_global_voice_leaderboard_sums_across_servers():
    await _schema()
    user = 990003
    await service.credit_voice([(770001, user, 1, 5), (770002, user, 9, 3)])  # two servers
    board = dict(await service.leaderboard_voice_global(50))
    assert board[user] == "0h 8m"  # 5 + 3 minutes, summed across both servers
