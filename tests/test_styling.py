"""Tests for the warm embed theme and the non-breaking emoji placeholders."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from discord.ext import commands

from src.core import embeds
from src.core.emojis import Emojis, _emoji

_USER = SimpleNamespace(
    display_name="nacrein", display_avatar=SimpleNamespace(url="https://e/a.png")
)

# ── emoji placeholders ──────────────────────────────────────────────────────

def test_unfilled_placeholder_renders_unicode_fallback():
    # id=0 is the "not uploaded yet" state — every reference must keep working.
    assert _emoji("bits", id=0, fallback="🪙") == "🪙"
    assert Emojis.SUCCESS == "✅"  # registry still resolves to working glyphs
    assert Emojis.ARROW_LEFT == "◀️"  # used as a button emoji — must stay valid


def test_filled_id_renders_custom_emoji_token():
    assert _emoji("bits", id=123456789012345678, fallback="🪙") == "<:bits:123456789012345678>"


def test_animated_filled_id_uses_a_prefix():
    got = _emoji("spin", id=42, fallback="🌀", animated=True)
    assert got == "<a:spin:42>"


def test_every_registry_value_is_a_nonempty_string():
    names = [n for n in vars(Emojis) if n.isupper()]
    assert names, "registry should expose emoji constants"
    for name in names:
        value = getattr(Emojis, name)
        assert isinstance(value, str) and value, f"{name} is empty"


# ── warm embed theme ────────────────────────────────────────────────────────

def test_palette_is_signature():
    assert embeds.COLOR_INFO == embeds.COLOR_SIGNATURE
    assert str(embeds.COLOR_SIGNATURE) == "#c56b5c"
    # Semantic colors stay distinct so errors still read as errors.
    assert len({
        str(embeds.COLOR_SUCCESS), str(embeds.COLOR_ERROR),
        str(embeds.COLOR_WARNING), str(embeds.COLOR_SIGNATURE),
    }) == 4


def test_builders_apply_color_and_title():
    e = embeds.success("done", "Title")
    assert e.color == embeds.COLOR_SUCCESS
    assert e.title == f"{Emojis.SUCCESS} Title"


def test_builders_omit_brand_footer_and_timestamp_by_default():
    # Command embeds carry no brand footer or timestamp unless a caller adds one.
    e = embeds.success("done", "Title")
    assert e.footer.text is None
    assert e.timestamp is None


def test_error_and_info_colors():
    assert embeds.error("boom").color == embeds.COLOR_ERROR
    assert embeds.info("", "Card").color == embeds.COLOR_SIGNATURE


def test_caller_can_override_brand_footer():
    e = embeds.info("body", "Title")
    e.set_footer(text="Page 1/2")  # functional footers must still win
    assert e.footer.text == "Page 1/2"


# ── author header (the house-style invoker row) ─────────────────────────────

def test_apply_author_sets_invoker_when_absent():
    e = embeds.info("hello")
    assert e.author.name is None
    embeds.apply_author(e, _USER)
    assert e.author.name == "nacrein"
    assert e.author.icon_url == "https://e/a.png"


def test_apply_author_never_overwrites_a_set_author():
    e = embeds.info("hello")
    e.set_author(name="original poster")  # e.g. snipe showing the OP
    embeds.apply_author(e, _USER)
    assert e.author.name == "original poster"


def test_apply_author_ignores_missing_user():
    e = embeds.info("hello")
    embeds.apply_author(e, None)
    assert e.author.name is None


async def test_botcontext_send_stamps_the_invoker():
    from src.core.bot import BotContext

    ctx = BotContext.__new__(BotContext)  # bypass the heavy Context __init__
    ctx.author = _USER
    captured = {}

    async def fake_super_send(self, content=None, **kwargs):
        captured["embed"] = kwargs.get("embed")
        return "sent"

    with patch.object(commands.Context, "send", fake_super_send):
        await ctx.send(embed=embeds.info("hi"))

    assert captured["embed"].author.name == "nacrein"
