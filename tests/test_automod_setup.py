"""Tests for the ,setup automod panel: layout, validators, render, invoker lock."""

from __future__ import annotations

from types import SimpleNamespace

import discord

from src.modules.automod.setup_view import (
    _DEFAULTS,
    AutomodSetupView,
    _EscalationModal,
    apply_escalation,
    apply_filter_limits,
    apply_words,
)


def test_layout_fits_five_rows_with_expected_controls():
    view = AutomodSetupView(1, 100)
    buttons = [c for c in view.children if isinstance(c, discord.ui.Button)]
    assert {b.label for b in buttons} == {
        "AutoMod: Off", "Mode: Dry-run", "Exempt mods: On",
        "Limits", "Escalation", "Add words", "Done", "Close",
    }
    assert len([c for c in view.children if isinstance(c, discord.ui.Select)]) == 1        # filter select
    assert len([c for c in view.children if isinstance(c, discord.ui.RoleSelect)]) == 1
    assert len([c for c in view.children if isinstance(c, discord.ui.ChannelSelect)]) == 1
    assert max(c._rendered_row if hasattr(c, "_rendered_row") else c.row or 0 for c in view.children) <= 4


def test_apply_filter_limits_valid_and_invalid():
    out = apply_filter_limits("5", "70 10", "8", "5 5", "3")
    assert out["mention_limit"] == 5 and out["caps_percent"] == 70 and out["caps_min_len"] == 10
    assert out["spam_count"] == 5 and out["spam_interval"] == 5 and out["duplicate_threshold"] == 3
    for args in (("0", "70 10", "8", "5 5", "3"),     # mention below min
                 ("5", "70", "8", "5 5", "3"),        # caps not two numbers
                 ("5", "70 10", "x", "5 5", "3"),     # emoji not a number
                 ("5", "40 10", "8", "5 5", "3")):    # caps percent below min
        try:
            apply_filter_limits(*args)
            assert False, f"expected {args} to raise"
        except ValueError:
            pass


def test_apply_escalation_valid_and_invalid():
    out = apply_escalation("24", "2 10", "3 60", "4", "5")
    assert out["strike_window_hours"] == 24 and out["timeout_at"] == 2 and out["ban_at"] == 5
    assert apply_escalation("24", "2 10", "3 60", "0", "0")["kick_at"] == 0   # 0 disables, allowed
    for args in (("0", "2 10", "3 60", "4", "5"),   # window below min
                 ("24", "2", "3 60", "4", "5")):    # timeout not two numbers
        try:
            apply_escalation(*args)
            assert False, f"expected {args} to raise"
        except ValueError:
            pass


def test_escalation_modal_does_not_shadow_reserved_timeout():
    # `timeout` is a reserved Modal attribute (float | None); a field named
    # `self.timeout` shadows it and crashes discord.py on send_modal with
    # "unsupported operand type(s) for +: 'float' and 'TextInput'".
    modal = _EscalationModal(AutomodSetupView(1, 100))
    assert modal.timeout is None
    labels = [i.label for i in modal.children]
    assert "Timeout 1: strikes and minutes" in labels
    assert "Timeout 2: strikes and minutes" in labels


def test_apply_words_splits_and_trims():
    assert apply_words("a\nb , c\n\n") == ["a", "b", "c"]
    try:
        apply_words("   ")
        assert False, "expected empty to raise"
    except ValueError:
        pass


def test_render_shows_live_vs_dry_run():
    view = AutomodSetupView(1, 100)
    assert "Dry-run" in {f.name: f.value for f in view.render().fields}["Mode"]  # default
    view._cfg = SimpleNamespace(**{**_DEFAULTS, "enabled": True, "log_only": False, "filter_invites": True})
    view._sync()
    fields = {f.name: f.value for f in view.render().fields}
    assert fields["Status"] == "On"
    assert "LIVE" in fields["Mode"]
    assert "invites" in fields["Filters on"]
    assert view._mode_btn.style is discord.ButtonStyle.danger


class _FakeResponse:
    def __init__(self) -> None:
        self.sent = None

    async def send_message(self, *args, **kwargs) -> None:
        self.sent = (args, kwargs)


async def test_only_invoker_may_use_panel():
    view = AutomodSetupView(1, 100)
    intruder = SimpleNamespace(user=SimpleNamespace(id=2), response=_FakeResponse())
    assert await view.interaction_check(intruder) is False
    assert intruder.response.sent[1].get("ephemeral") is True
