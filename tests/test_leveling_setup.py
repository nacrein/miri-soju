"""Tests for the ,setup levels panel — control layout, validation, and rendering.

No live Discord: we build the view, drive its sync ``apply_*`` helpers and
``_sync``/``render`` from a fake config, and check the author lock — the same
pattern as the embed-builder tests.
"""

from __future__ import annotations

from types import SimpleNamespace

import discord

from src.modules.leveling import config
from src.modules.leveling.setup_view import LevelingSetupView, apply_message, apply_xp


def _fake_cfg(**over):
    base = dict(
        enabled=True, xp_per_message=25, message_cooldown=45,
        announce_mode="here", announce_channel_id=None,
        level_up_message="gg {user}",
    )
    base.update(over)
    return SimpleNamespace(**base)


# ── control layout ────────────────────────────────────────────────────────────

def test_view_has_the_expected_controls():
    view = LevelingSetupView(1, 100)
    buttons = [c for c in view.children if isinstance(c, discord.ui.Button)]
    selects = [c for c in view.children if isinstance(c, discord.ui.ChannelSelect)]
    assert len(selects) == 1  # the announce-channel picker (ChannelSelect, not a value Select)
    assert {b.label for b in buttons} == {
        "Leveling: Off", "XP settings", "Level-up message",
        "Announce: Here", "Announce: DM", "Done", "Close",
    }
    # every control fits inside Discord's 5 action rows
    assert max(c._rendered_row if hasattr(c, "_rendered_row") else c.row or 0 for c in view.children) <= 4


# ── modal validation (sync, no Discord) ───────────────────────────────────────

def test_apply_xp_accepts_in_range_and_returns_ints():
    assert apply_xp("30", "90") == (30, 90)
    assert apply_xp(f" {config.RATE_MAX} ", f"{config.COOLDOWN_MIN}") == (config.RATE_MAX, 0)


def test_apply_xp_rejects_out_of_range_and_non_numbers():
    for rate, cd in (("0", "60"), ("1001", "60"), ("20", "-1"), ("20", "3601"), ("x", "60")):
        try:
            apply_xp(rate, cd)
            assert False, f"expected ({rate}, {cd}) to raise"
        except ValueError:
            pass


def test_apply_message_trims_and_bounds():
    assert apply_message("  hi {user}  ") == "hi {user}"
    for bad in ("", "   ", "x" * (config.MESSAGE_MAX + 1)):
        try:
            apply_message(bad)
            assert False, f"expected {bad!r} to raise"
        except ValueError:
            pass


# ── render / sync from a fake config ──────────────────────────────────────────

def test_sync_reflects_enabled_and_announce_mode():
    view = LevelingSetupView(1, 100)
    view._cfg = _fake_cfg(enabled=True, announce_mode="dm")
    view._sync()
    assert view._enabled_btn.label == "Leveling: On"
    assert view._enabled_btn.style is discord.ButtonStyle.success
    assert view._dm_btn.style is discord.ButtonStyle.primary
    assert view._here_btn.style is discord.ButtonStyle.secondary


def test_render_shows_config_values():
    view = LevelingSetupView(1, 100)
    view._cfg = _fake_cfg(xp_per_message=25, message_cooldown=45, announce_mode="channel",
                          announce_channel_id=999)
    view._reward_count, view._mult_count = 2, 1
    e = view.render()
    assert "Leveling Setup" in e.title
    fields = {f.name: f.value for f in e.fields}
    assert fields["Status"] == "On"
    assert fields["XP / message"] == "25"
    assert fields["Cooldown"] == "45s"
    assert fields["Announce"] == "<#999>"
    assert fields["Rewards"] == "2"


def test_render_falls_back_to_defaults_without_a_config_row():
    view = LevelingSetupView(1, 100)  # _cfg is None
    e = view.render()
    fields = {f.name: f.value for f in e.fields}
    assert fields["Status"] == "Off"
    assert fields["XP / message"] == str(config.XP_PER_MESSAGE)


# ── locked to the invoker ─────────────────────────────────────────────────────

class _FakeResponse:
    def __init__(self) -> None:
        self.sent = None

    async def send_message(self, *args, **kwargs) -> None:
        self.sent = (args, kwargs)


def _interaction(uid: int):
    return SimpleNamespace(user=SimpleNamespace(id=uid), response=_FakeResponse())


async def test_only_the_invoker_may_use_the_panel():
    view = LevelingSetupView(1, 100)
    intruder = _interaction(2)
    assert await view.interaction_check(intruder) is False
    assert intruder.response.sent[1].get("ephemeral") is True
    assert await view.interaction_check(_interaction(1)) is True
