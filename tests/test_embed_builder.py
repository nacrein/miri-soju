"""Tests for the interactive embed builder and its JSON script core.

No live Discord: we construct the view, assert on its ``.children`` and on the
rendered preview, and call the synchronous ``apply_*`` mutation methods the modals
delegate to — the same pattern the help-view tests use.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import discord

from src.modules.embed import script
from src.modules.embed.views import EmbedBuilderView


# ── the script core: build / to_script ───────────────────────────────────────

def test_build_roundtrips_through_to_script():
    data = {
        "title": "Hi", "description": "Body", "color": "#5865f2",
        "footer": "ft", "fields": [{"name": "n", "value": "v", "inline": True}],
    }
    out = script.to_script(script.build(data))
    assert out["title"] == "Hi"
    assert out["description"] == "Body"
    assert out["color"] == "#5865f2"
    assert out["fields"] == [{"name": "n", "value": "v", "inline": True}]


def test_build_rejects_empty_and_bad_color():
    for bad in ({}, {"title": ""}, {"fields": []}):
        try:
            script.build(bad)
            assert False, f"expected empty embed to raise: {bad}"
        except ValueError:
            pass
    try:
        script.build({"title": "x", "color": "not-a-color"})
        assert False, "expected bad color to raise"
    except ValueError as exc:
        assert "hex" in str(exc)


def test_build_clamps_to_field_limits():
    e = script.build({"title": "T" * 999, "description": "D" * 99999})
    assert len(e.title) == script.TITLE_MAX
    assert len(e.description) == script.DESCRIPTION_MAX  # 4000, not Discord's 4096
    # exactly 25 fields is allowed (the boundary); >25 raises — see
    # test_build_rejects_too_many_fields
    e2 = script.build({"fields": [{"name": "n", "value": "v"} for _ in range(script.MAX_FIELDS)]})
    assert len(e2.fields) == script.MAX_FIELDS


def test_parse_bool_is_forgiving():
    assert all(script.parse_bool(s) for s in ("yes", "Y", "true", "1", "on"))
    assert not any(script.parse_bool(s) for s in ("no", "", "nope", None))


def test_build_accepts_integer_colors():
    # third-party embed JSON often stores color as a decimal int
    e = script.build({"title": "x", "color": "5793266"})
    assert e.color == discord.Color.from_str("#5865f2")
    assert script.to_script(e)["color"] == "#5865f2"  # normalized on the way out


def test_build_rejects_too_many_fields():
    try:
        script.build({"fields": [{"name": "n", "value": "v"} for _ in range(26)]})
        assert False, "expected >25 fields to raise"
    except ValueError as exc:
        assert "25" in str(exc)


def test_build_uses_placeholder_for_blank_field_text():
    # whitespace-only name/value would be rejected by Discord; build substitutes ​
    e = script.build({"title": "t", "fields": [{"name": "   ", "value": "  "}]})
    assert e.fields[0].name == "​"
    assert e.fields[0].value == "​"


# ── the view: control layout ─────────────────────────────────────────────────

def test_view_has_the_expected_controls():
    view = EmbedBuilderView(1)
    buttons = [c for c in view.children if isinstance(c, discord.ui.Button)]
    selects = [c for c in view.children if isinstance(c, discord.ui.Select)]
    assert len(selects) == 1            # the field dropdown
    labels = {b.label for b in buttons}
    assert labels == {
        "Content", "Author & footer", "Images",
        "Add field", "Import JSON", "Export JSON", "Send", "Cancel",
    }
    # every control fits inside Discord's 5 action rows
    assert max(c._rendered_row if hasattr(c, "_rendered_row") else c.row or 0 for c in view.children) <= 4


def test_field_select_is_disabled_until_there_are_fields():
    view = EmbedBuilderView(1)
    assert view._field_select.disabled is True
    assert len(view._field_select.options) == 1  # a Select must always have ≥1 option
    view.apply_add_field("n", "v", "no")
    view._sync()
    assert view._field_select.disabled is False
    assert [o.value for o in view._field_select.options] == ["0"]


def _send_button(view: EmbedBuilderView) -> discord.ui.Button:
    return next(b for b in view.children if isinstance(b, discord.ui.Button) and b.label == "Send")


def test_send_is_disabled_while_empty_then_enabled():
    view = EmbedBuilderView(1)
    assert _send_button(view).disabled is True
    view.apply_content("Hello", "", "", "")
    view._sync()
    assert _send_button(view).disabled is False


# ── the view: rendering never raises ─────────────────────────────────────────

def test_render_shows_a_guide_card_when_empty():
    e = EmbedBuilderView(1).render()
    assert "Embed builder" in e.title
    assert "empty" in e.description.lower()


def test_render_shows_the_real_embed_once_filled():
    view = EmbedBuilderView(1)
    view.apply_content("My Title", "My body", "", "#5865f2")
    e = view.render()
    assert e.title == "My Title"
    assert e.color == discord.Color.from_str("#5865f2")


# ── the view: mutations the modals delegate to ───────────────────────────────

def test_apply_content_sets_and_clears_keys():
    view = EmbedBuilderView(1)
    view.apply_content("T", "D", "https://x", "#010203")
    assert view.data == {"title": "T", "description": "D", "url": "https://x", "color": "#010203"}
    view.apply_content("", "", "", "")  # blanks remove the keys
    assert view.data == {}


def test_apply_content_rejects_bad_color_without_storing():
    view = EmbedBuilderView(1)
    try:
        view.apply_content("T", "", "", "purple-ish")
        assert False, "expected bad color to raise"
    except ValueError:
        pass
    assert "color" not in view.data


def test_apply_add_and_edit_and_delete_fields():
    view = EmbedBuilderView(1)
    view.apply_add_field("first", "v1", "yes")
    assert view.data["fields"] == [{"name": "first", "value": "v1", "inline": True}]
    view.apply_edit_field(0, "renamed", "v2", "no", "")
    assert view.data["fields"] == [{"name": "renamed", "value": "v2", "inline": False}]
    view.apply_edit_field(0, "renamed", "v2", "no", "yes")  # delete
    assert "fields" not in view.data


def test_add_field_enforces_the_cap():
    view = EmbedBuilderView(1)
    for i in range(script.MAX_FIELDS):
        view.apply_add_field(f"n{i}", "v", "no")
    try:
        view.apply_add_field("overflow", "v", "no")
        assert False, "expected the 26th field to raise"
    except ValueError:
        pass


def test_apply_import_replaces_or_rejects():
    view = EmbedBuilderView(1)
    view.apply_import('{"title": "Imported"}')
    assert view.data["title"] == "Imported"
    # fenced JSON pastes (what ,ec emits) are accepted
    view.apply_import('```json\n{"description": "fenced"}\n```')
    assert view.data == {"description": "fenced"}
    for bad in ("{not json", "{}"):  # invalid syntax, and a valid-but-empty embed
        try:
            view.apply_import(bad)
            assert False, f"expected {bad!r} to raise"
        except ValueError:
            pass


def test_apply_import_clamps_and_bounds_so_modals_can_reopen():
    view = EmbedBuilderView(1)
    # over-long values must be stored clamped, or the edit modal (max_length) breaks
    view.apply_import(json.dumps({"title": "x" * 999, "description": "y" * 99999}))
    assert len(view.data["title"]) == script.TITLE_MAX
    assert len(view.data["description"]) == script.DESCRIPTION_MAX
    # too many fields is rejected outright (not silently truncated on Send)
    try:
        view.apply_import(json.dumps({"fields": [{"name": "n", "value": "v"} for _ in range(30)]}))
        assert False, "expected >25 imported fields to raise"
    except ValueError:
        pass


def test_field_at_guards_a_stale_selection():
    view = EmbedBuilderView(1)
    view.apply_add_field("only", "v", "no")
    assert view._field_at(0) == {"name": "only", "value": "v", "inline": False}
    assert view._field_at(5) is None   # a dropdown click after the field was removed
    assert view._field_at(-1) is None


# ── the view: locked to the invoker ──────────────────────────────────────────

class _FakeResponse:
    def __init__(self) -> None:
        self.sent = None

    async def send_message(self, *args, **kwargs) -> None:
        self.sent = (args, kwargs)


def _interaction(uid: int):
    return SimpleNamespace(user=SimpleNamespace(id=uid), response=_FakeResponse())


async def test_only_the_invoker_may_use_the_builder():
    view = EmbedBuilderView(1)
    intruder = _interaction(2)
    assert await view.interaction_check(intruder) is False
    assert intruder.response.sent[1].get("ephemeral") is True
    assert await view.interaction_check(_interaction(1)) is True
