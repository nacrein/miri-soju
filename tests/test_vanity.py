"""Tests for vanity rep: the gate, presence detection, the reconcile diff, the panel.

Pure/no live Discord, with SimpleNamespace fakes for the discord-typed helpers."""

from __future__ import annotations

from types import SimpleNamespace

import discord

from src.modules.vanity import service
from src.modules.vanity.cog import _is_repping
from src.modules.vanity.gate import has_vanity
from src.modules.vanity.setup_view import VanitySetupView


# ── the gate ────────────────────────────────────────────────────────────────────

def test_has_vanity_checks_code_or_feature_flag():
    assert has_vanity(SimpleNamespace(vanity_url_code="myserver", features=[])) is True
    assert has_vanity(SimpleNamespace(vanity_url_code=None, features=["VANITY_URL"])) is True
    assert has_vanity(SimpleNamespace(vanity_url_code=None, features=[])) is False
    assert has_vanity(SimpleNamespace(vanity_url_code="", features=["COMMUNITY"])) is False


# ── presence detection ──────────────────────────────────────────────────────────

def _member(status, *texts):
    activities = [discord.CustomActivity(name=t) for t in texts]
    return SimpleNamespace(status=status, activities=activities)


def test_is_repping_detects_vanity_in_custom_status():
    assert _is_repping(_member(discord.Status.online, "join discord.gg/MyServer!"), "myserver") is True
    assert _is_repping(_member(discord.Status.online, ".gg/myserver"), "myserver") is True
    assert _is_repping(_member(discord.Status.dnd, "playing a game"), "myserver") is False
    assert _is_repping(_member(discord.Status.online), "myserver") is False           # no custom status
    assert _is_repping(_member(discord.Status.offline, ".gg/myserver"), "myserver") is False  # offline/invisible


# ── the pure reconcile diff ─────────────────────────────────────────────────────

async def test_reconcile_targets_set_math(monkeypatch):
    async def fake_active(_guild_id):
        return {1, 2, 3}
    monkeypatch.setattr(service, "get_active_ids", fake_active)
    to_grant, to_revoke = await service.reconcile_targets(99, {2, 3, 4})
    assert to_grant == {4}    # live but not stored
    assert to_revoke == {1}   # stored but no longer live


# ── setup panel ─────────────────────────────────────────────────────────────────

def test_panel_layout():
    view = VanitySetupView(1, 100)
    buttons = [c for c in view.children if isinstance(c, discord.ui.Button)]
    assert {b.label for b in buttons} == {"Vanity rep: Off", "Message", "Done", "Close"}
    assert len([c for c in view.children if isinstance(c, discord.ui.RoleSelect)]) == 1
    assert len([c for c in view.children if isinstance(c, discord.ui.ChannelSelect)]) == 1
    assert max(c._rendered_row if hasattr(c, "_rendered_row") else c.row or 0 for c in view.children) <= 4


def test_panel_render():
    view = VanitySetupView(1, 100)
    view._cfg = SimpleNamespace(enabled=True, role_id=7, channel_id=8, message_template=None)
    view._count = 5
    view._sync()
    assert view._enabled_btn.style is discord.ButtonStyle.success
    fields = {f.name: f.value for f in view.render().fields}
    assert fields["Status"] == "On"
    assert fields["Reward role"] == "<@&7>"
    assert fields["Currently repping"] == "5"
