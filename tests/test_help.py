"""Tests for the auto-updating, card-styled help system.

These lock in that help is derived from the live registry (each command renders
as a card; picking a category lists all of its commands in one codeblock), that
the menu groups into the curated categories, and that the templates render right.
"""

from __future__ import annotations

import importlib
import pkgutil
from types import SimpleNamespace

import discord
from discord.ext import commands

from src.core.help_format import (
    command_card,
    command_family,
    command_listing,
    subcommands_of,
    usage_line,
)
from src.core.paginator import CommandBrowser
from src.database.base import Base
from src.database.session import engine
from src.modules.help.views import HelpMenu


async def _loaded_bot() -> commands.Bot:
    from src.core.bot import Bot

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    bot = Bot()
    pkg = importlib.import_module("src.modules")
    for info in pkgutil.walk_packages(pkg.__path__, "src.modules."):
        if info.ispkg:
            continue
        mod = importlib.import_module(info.name)
        if hasattr(mod, "setup"):
            try:
                await bot.load_extension(info.name)
            except commands.ExtensionAlreadyLoaded:
                pass
    return bot


async def _unload(bot: commands.Bot) -> None:
    for ext in list(bot.extensions):
        await bot.unload_extension(ext)


_FAKE_AUTHOR = SimpleNamespace(
    display_name="nacrein",
    display_avatar=SimpleNamespace(url="https://example.com/a.png"),
)


# ── the card template ───────────────────────────────────────────────────────

async def test_command_card_shape():
    bot = await _loaded_bot()
    try:
        ban = bot.get_command("ban")
        e = command_card(
            ban, ",", author=_FAKE_AUTHOR, category="Moderation", page=1, total=5,
        )
        assert e.author.name == "nacrein"
        d = e.description
        assert d.startswith("## Command: ban")  # markdown heading, not embed title
        assert "\n> " in d  # blockquoted help
        assert "```ansi" in d and "Syntax: ,ban" in d  # ansi syntax panel
        assert e.footer.text == "Moderation · page 1/5 (5 entries)"
    finally:
        await _unload(bot)


async def test_group_card_marks_a_subcommand_token():
    bot = await _loaded_bot()
    try:
        vault = bot.get_command("vault")
        assert isinstance(vault, commands.Group)
        d = command_card(vault, ",").description
        assert "```ansi" in d
        assert "<subcommand>" in d  # the syntax panel marks it as a group
    finally:
        await _unload(bot)


# ── family pagination (next → subcommand) ───────────────────────────────────

async def test_command_family_is_parent_then_subcommands():
    bot = await _loaded_bot()
    try:
        role = bot.get_command("role")
        family = command_family(role)
        assert family[0] is role
        names = [c.qualified_name for c in family]
        for sub in subcommands_of(role):
            assert sub.qualified_name in names
        # a plain command is a family of one
        assert command_family(bot.get_command("ban")) == [bot.get_command("ban")]
    finally:
        await _unload(bot)


async def test_command_listing_names_commands_and_marks_groups():
    bot = await _loaded_bot()
    try:
        vault = bot.get_command("vault")  # a group
        ban = bot.get_command("ban")      # a plain command
        listing = command_listing([vault, ban])
        # one ansi codeblock
        assert listing.startswith("```ansi") and listing.rstrip().endswith("```")
        # a group shows its visible-subcommand count and the `..` marker
        assert f"vault ({len(subcommands_of(vault))}).." in listing
        # a plain command is just its name (no count marker)
        assert "ban" in listing and "ban (" not in listing
    finally:
        await _unload(bot)


# ── command browser (what a bare group / ,help <group> shows) ────────────────

async def test_command_browser_pages_family_with_four_buttons():
    bot = await _loaded_bot()
    try:
        role = bot.get_command("role")
        family = command_family(role)
        view = CommandBrowser(1, family, "Moderation", ",", invoker=_FAKE_AUTHOR)
        buttons = [c for c in view.children if isinstance(c, discord.ui.Button)]
        assert len(buttons) == 4  # prev, next, search, close
        first = view.card()
        assert first.description.startswith(f"## Command: {family[0].qualified_name}")
        assert first.footer.text == f"Moderation · page 1/{len(family)} ({len(family)} entries)"
        # advancing lands on the next family member
        view._index = 1
        assert view.card().description.startswith(f"## Command: {family[1].qualified_name}")
    finally:
        await _unload(bot)


async def test_command_browser_search_matches_by_name():
    bot = await _loaded_bot()
    try:
        role = bot.get_command("role")
        family = command_family(role)
        view = CommandBrowser(1, family, "Moderation", ",", invoker=_FAKE_AUTHOR)
        sub = subcommands_of(role)[0]
        assert view.match_index(sub.qualified_name) == family.index(sub)  # exact wins
        assert view.match_index(sub.name) is not None  # bare subname via substring
        assert view.match_index("definitely-not-a-command") is None
    finally:
        await _unload(bot)


# ── usage line signals groups ───────────────────────────────────────────────

@commands.group(name="demo_grp")
async def _demo_group(ctx):  # pragma: no cover - body never runs
    ...


@_demo_group.command(name="sub")
async def _demo_sub(ctx):  # pragma: no cover - body never runs
    ...


def test_usage_line_marks_groups_and_not_plain_commands():
    assert usage_line(_demo_group, ",").endswith("<subcommand>")
    assert not usage_line(_demo_sub, ",").endswith("<subcommand>")


async def test_usage_line_matches_required_and_marks_variadic():
    bot = await _loaded_bot()
    try:
        # required <user> + optional [reason] (consume-rest)
        assert usage_line(bot.get_command("ban"), ",") == ",ban <user> [reason]"
        # *user_ids → repeatable
        assert "<user_ids…>" in usage_line(bot.get_command("massban"), ",")
        # every param classification agrees with discord.py's own param.required
        for cmd in bot.walk_commands():
            if cmd.hidden:
                continue
            line = usage_line(cmd, ",")
            for name, param in cmd.clean_params.items():
                bracket = "<" if param.required else "["
                assert f"{bracket}{name}" in line, f"{cmd.qualified_name}:{name}"
    finally:
        await _unload(bot)


# ── curated categories (the few-dropdowns grouping) ─────────────────────────

async def test_menu_uses_only_curated_categories_in_order():
    from src.modules.help.categories import CATEGORIES, DEFAULT_CATEGORY

    bot = await _loaded_bot()
    try:
        cats = bot.get_cog("Help")._categories()
        assert set(cats) <= set(CATEGORIES)
        assert list(cats) == [c for c in CATEGORIES if c in cats]
        assert len(cats) <= 7, "the whole point is a short menu"
        assert DEFAULT_CATEGORY in CATEGORIES
    finally:
        await _unload(bot)


async def test_no_command_is_dropped_by_categorization():
    bot = await _loaded_bot()
    try:
        cats = bot.get_cog("Help")._categories()
        grouped = sum(len(v) for v in cats.values())
        live = sum(
            1 for cog in bot.cogs.values() for c in cog.get_commands() if not c.hidden
        )
        live += sum(1 for c in bot.commands if c.cog is None and not c.hidden)
        assert grouped == live
    finally:
        await _unload(bot)


async def test_known_cogs_route_to_expected_categories():
    bot = await _loaded_bot()
    try:
        cats = bot.get_cog("Help")._categories()

        def category_of(cmd_name: str) -> str:
            cmd = bot.get_command(cmd_name)
            assert cmd is not None, f"{cmd_name} not registered"
            return next(name for name, cmds in cats.items() if cmd in cmds)

        assert category_of("vault") == "Economy"
        assert category_of("levels") == "Leveling"
        assert category_of("ban") == "Moderation"
        assert category_of("staff") == "Moderation"
        assert category_of("webhook") == "Server Setup"
        assert category_of("emoji") == "Utility"
        assert category_of("help") == "Bot"
    finally:
        await _unload(bot)


# ── menu view: category dropdown(s), chunked under Discord's caps ────────────

async def test_menu_is_only_category_dropdowns_no_buttons():
    bot = await _loaded_bot()
    try:
        cats = bot.get_cog("Help")._categories()
        menu = HelpMenu(1, cats, ",", invoker=_FAKE_AUTHOR)
        selects = [c for c in menu.children if isinstance(c, discord.ui.Select)]
        buttons = [c for c in menu.children if isinstance(c, discord.ui.Button)]
        assert len(selects) == 1
        assert len(selects[0].options) == len(cats)
        assert buttons == []  # the ◀ ▶ pager arrows are gone
    finally:
        await _unload(bot)


async def test_picking_a_category_lists_its_commands_in_one_codeblock():
    bot = await _loaded_bot()
    try:
        cats = bot.get_cog("Help")._categories()
        menu = HelpMenu(1, cats, ",", invoker=_FAKE_AUTHOR)
        e = menu.category_embed("Economy")
        assert "## `Economy` commands" in e.description
        assert "```ansi" in e.description  # a single codeblock, not paged cards
        # footer counts the category's top-level commands and how many are groups
        groups = sum(1 for c in cats["Economy"] if isinstance(c, commands.Group))
        assert e.footer.text == f"{len(cats['Economy'])} commands · {groups} groups"
        assert e.author.name == "nacrein"  # house-style invoker row is kept
    finally:
        await _unload(bot)


def test_help_menu_chunks_beyond_25_categories():
    cats = {f"Cat{i:02d}": [] for i in range(30)}
    menu = HelpMenu(1, cats, ",")
    selects = [ch for ch in menu.children if isinstance(ch, discord.ui.Select)]
    assert len(selects) == 2, "30 categories should split into two dropdowns"
    assert all(len(s.options) <= 25 for s in selects)
    assert sum(len(s.options) for s in selects) == 30, "no category may be dropped"
