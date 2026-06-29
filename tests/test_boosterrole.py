"""Tests for booster roles: color parsing, the setup panel, and the invoker lock.

Pure/no live Discord, following the existing view-test style."""

from __future__ import annotations

from types import SimpleNamespace

import discord

from src.core.errors import BotError
from src.modules.boosterrole import service
from src.modules.boosterrole.setup_view import BoosterRoleSetupView

# ── parse_color ────────────────────────────────────────────────────────────────

def test_parse_color_accepts_all_forms():
    assert service.parse_color("#aabbcc") == 0xAABBCC
    assert service.parse_color("aabbcc") == 0xAABBCC
    assert service.parse_color("#abc") == 0xAABBCC      # shorthand expands
    assert service.parse_color("abc") == 0xAABBCC
    assert service.parse_color("  #5865F2  ") == 0x5865F2  # trimmed, case-insensitive
    assert service.parse_color("#000000") == 0
    assert service.parse_color("ffffff") == 0xFFFFFF


def test_parse_color_rejects_bad_input():
    for bad in ("", "#", "12345", "#1234567", "ggg", "#xyzxyz", "red"):
        try:
            service.parse_color(bad)
            assert False, f"expected {bad!r} to raise"
        except BotError:
            pass


# ── setup panel ────────────────────────────────────────────────────────────────

def _fake_cfg(**over):
    base = dict(enabled=True, hoist_above=True, anchor_role_id=None)
    base.update(over)
    return SimpleNamespace(**base)


def test_panel_layout():
    view = BoosterRoleSetupView(1, 100)
    buttons = [c for c in view.children if isinstance(c, discord.ui.Button)]
    assert {b.label for b in buttons} == {"Booster roles: Off", "Hoist: Above anchor", "Done", "Close"}
    assert len([c for c in view.children if isinstance(c, discord.ui.RoleSelect)]) == 1
    assert max(c._rendered_row if hasattr(c, "_rendered_row") else c.row or 0 for c in view.children) <= 4


def test_panel_render_and_sync():
    view = BoosterRoleSetupView(1, 100)
    view._cfg = _fake_cfg(enabled=True, hoist_above=False, anchor_role_id=999)
    view._count = 3
    view._sync()
    assert view._enabled_btn.style is discord.ButtonStyle.success
    assert view._hoist_btn.label == "Hoist: Below anchor"
    fields = {f.name: f.value for f in view.render().fields}
    assert fields["Status"] == "On"
    assert fields["Hoist"] == "Below anchor"
    assert fields["Anchor"] == "<@&999>"
    assert fields["Booster roles"] == "3"


def test_panel_defaults_without_config():
    view = BoosterRoleSetupView(1, 100)  # _cfg is None
    fields = {f.name: f.value for f in view.render().fields}
    assert fields["Status"] == "Off"
    assert fields["Hoist"] == "Above anchor"
    assert fields["Anchor"] == "Not set"


class _FakeResponse:
    def __init__(self) -> None:
        self.sent = None

    async def send_message(self, *args, **kwargs) -> None:
        self.sent = (args, kwargs)


async def test_only_invoker_may_use_panel():
    view = BoosterRoleSetupView(1, 100)
    intruder = SimpleNamespace(user=SimpleNamespace(id=2), response=_FakeResponse())
    assert await view.interaction_check(intruder) is False
    assert intruder.response.sent[1].get("ephemeral") is True
