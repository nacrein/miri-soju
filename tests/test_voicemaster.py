"""Tests for VoiceMaster: panel layout, the in-memory timing state, and setup panel.

Pure/no live Discord, following the existing view-test style."""

from __future__ import annotations

from types import SimpleNamespace

import discord

from src.modules.voicemaster import config, state
from src.modules.voicemaster.setup_view import VoiceMasterSetupView
from src.modules.voicemaster.views import VoicePanelView, panel_embed

# ── persistent panel layout ────────────────────────────────────────────────────

def test_panel_has_eight_buttons_with_static_ids_across_two_rows():
    view = VoicePanelView()
    buttons = [c for c in view.children if isinstance(c, discord.ui.Button)]
    assert len(buttons) == 8
    assert {b.custom_id for b in buttons} == {
        "vm:rename", "vm:limit", "vm:lock", "vm:unlock",
        "vm:hide", "vm:reveal", "vm:transfer", "vm:claim",
    }
    assert view.timeout is None  # persistent
    assert max(b._rendered_row if hasattr(b, "_rendered_row") else b.row or 0 for b in buttons) <= 1


def test_panel_embed_titles_voicemaster():
    assert "VoiceMaster" in panel_embed().title


# ── timing state ────────────────────────────────────────────────────────────────

def test_rename_rate_limit_two_per_window():
    cid = 555001
    assert state.rename_allowed(cid) is True
    state.record_rename(cid)
    assert state.rename_allowed(cid) is True   # 1 used
    state.record_rename(cid)
    assert state.rename_allowed(cid) is False   # bucket full (RENAME_MAX == 2)
    state.forget_channel(cid)
    assert state.rename_allowed(cid) is True     # reset on delete


def test_rename_max_is_two():
    assert config.RENAME_MAX == 2


def test_create_cooldown_per_user():
    g, u, other = 700, 800, 801
    assert state.on_create_cooldown(g, u) is False
    state.mark_create(g, u)
    assert state.on_create_cooldown(g, u) is True
    assert state.on_create_cooldown(g, other) is False  # independent per user


# ── setup panel ────────────────────────────────────────────────────────────────

def test_setup_panel_layout():
    view = VoiceMasterSetupView(1, 100)
    buttons = [c for c in view.children if isinstance(c, discord.ui.Button)]
    assert {b.label for b in buttons} == {"VoiceMaster: Off", "Done", "Close"}
    assert len([c for c in view.children if isinstance(c, discord.ui.ChannelSelect)]) == 2
    assert max(c._rendered_row if hasattr(c, "_rendered_row") else c.row or 0 for c in view.children) <= 4


def test_setup_panel_render():
    view = VoiceMasterSetupView(1, 100)
    view._cfg = SimpleNamespace(enabled=True, create_channel_id=42, panel_message_id=99)
    view._tracked = 2
    view._sync()
    assert view._enabled_btn.style is discord.ButtonStyle.success
    fields = {f.name: f.value for f in view.render().fields}
    assert fields["Status"] == "On"
    assert fields["Create channel"] == "<#42>"
    assert fields["Panel"] == "Posted"
    assert fields["Active channels"] == "2"
