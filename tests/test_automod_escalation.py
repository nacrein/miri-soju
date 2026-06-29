"""Tests for the escalation mapping, the fool-proof exemption gate, and the spam tracker.

No live Discord/DB: ``is_exempt`` is driven with SimpleNamespace fakes and the
moderation immune/staff lookups are monkeypatched.
"""

from __future__ import annotations

from types import SimpleNamespace

from src.core import checks
from src.modules.automod import service
from src.modules.automod.config import action_for
from src.modules.automod.enforcement import is_exempt
from src.modules.moderation import service as mod_service


def _cfg(**over):
    base = dict(timeout_at=2, timeout_minutes=10, timeout2_at=3, timeout2_minutes=60,
                kick_at=4, ban_at=5, exempt_mods=True)
    base.update(over)
    return SimpleNamespace(**base)


# ── escalation mapping ─────────────────────────────────────────────────────────

def test_action_for_default_ladder():
    cfg = _cfg()
    assert action_for(1, cfg) == ("warn", None)
    assert action_for(2, cfg) == ("timeout", 10)
    assert action_for(3, cfg) == ("timeout", 60)
    assert action_for(4, cfg) == ("kick", None)
    assert action_for(5, cfg) == ("ban", None)
    assert action_for(9, cfg) == ("ban", None)


def test_action_for_disabled_tier_falls_through():
    cfg = _cfg(ban_at=0)              # no ban tier
    assert action_for(5, cfg) == ("kick", None)
    cfg2 = _cfg(ban_at=0, kick_at=0)  # no ban, no kick
    assert action_for(9, cfg2) == ("timeout", 60)


# ── exemption gate ─────────────────────────────────────────────────────────────

def _perms(**kw):
    base = dict(manage_messages=False, manage_guild=False, administrator=False)
    base.update(kw)
    return SimpleNamespace(**base)


def _bot(uid=999):
    async def _not_owner(_user):
        return False
    return SimpleNamespace(user=SimpleNamespace(id=uid), is_owner=_not_owner)


def _guild(owner_id=111, bot_top=5):
    return SimpleNamespace(id=1, owner_id=owner_id,
                           me=SimpleNamespace(top_role=bot_top, guild_permissions=_perms()))


def _member(**over):
    base = dict(bot=False, id=222, roles=[SimpleNamespace(id=333)], top_role=1,
                guild_permissions=_perms())
    base.update(over)
    return SimpleNamespace(**base)


async def _not_immune(_g, _t, _r):
    return False


async def test_plain_member_is_not_exempt(monkeypatch):
    monkeypatch.setattr(mod_service, "is_immune", _not_immune)
    monkeypatch.setattr(checks, "_staff_ids", set)
    assert await is_exempt(_bot(), _guild(), _member(), _cfg(), set(), set(), 7) is False


async def test_each_protection_exempts(monkeypatch):
    monkeypatch.setattr(mod_service, "is_immune", _not_immune)
    monkeypatch.setattr(checks, "_staff_ids", set)
    g = _guild()
    assert await is_exempt(_bot(), g, _member(bot=True), _cfg(), set(), set(), 7) is True       # a bot
    assert await is_exempt(_bot(uid=222), g, _member(id=222), _cfg(), set(), set(), 7) is True   # the bot itself
    assert await is_exempt(_bot(), g, _member(id=111), _cfg(), set(), set(), 7) is True          # guild owner
    assert await is_exempt(_bot(), g, _member(), _cfg(), set(), {7}, 7) is True                  # exempt channel
    assert await is_exempt(_bot(), g, _member(), _cfg(), {333}, set(), 7) is True                # exempt role
    assert await is_exempt(_bot(), g, _member(top_role=10), _cfg(), set(), set(), 7) is True     # above the bot
    mod = _member(guild_permissions=_perms(manage_messages=True))
    assert await is_exempt(_bot(), g, mod, _cfg(), set(), set(), 7) is True                      # mod perms
    assert await is_exempt(_bot(), g, mod, _cfg(exempt_mods=False), set(), set(), 7) is False    # …unless off


async def test_staff_and_immune_exempt(monkeypatch):
    monkeypatch.setattr(checks, "_staff_ids", lambda: {222})
    monkeypatch.setattr(mod_service, "is_immune", _not_immune)
    assert await is_exempt(_bot(), _guild(), _member(), _cfg(), set(), set(), 7) is True  # staff

    monkeypatch.setattr(checks, "_staff_ids", set)

    async def _immune(_g, _t, _r):
        return True
    monkeypatch.setattr(mod_service, "is_immune", _immune)
    assert await is_exempt(_bot(), _guild(), _member(), _cfg(), set(), set(), 7) is True  # immune list


# ── spam tracker ───────────────────────────────────────────────────────────────

def test_flood_tracker_trips_at_count():
    g, u = 10, 20
    results = [service.record_and_check_flood(g, u, 5, 5) for _ in range(5)]
    assert results[:4] == [False, False, False, False]
    assert results[4] is True


def test_duplicate_tracker_trips_and_resets():
    g, u = 11, 21
    assert service.record_and_check_duplicate(g, u, "hello", 3) is False
    assert service.record_and_check_duplicate(g, u, "hello", 3) is False
    assert service.record_and_check_duplicate(g, u, "hello", 3) is True
    assert service.record_and_check_duplicate(g, u, "different", 3) is False  # reset on change
