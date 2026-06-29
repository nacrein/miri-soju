"""Commands resolve regardless of capitalisation — top-level and subcommands.

Phone keyboards auto-capitalise the first word, so ``,Setup`` and ``,Levels Enable``
must work the same as the lowercase forms. (discord.py already skips whitespace
after the prefix, so spacing needs no test.)
"""

from __future__ import annotations

import importlib
import pkgutil

from discord.ext import commands

from src.database.base import Base
from src.database.session import engine


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


async def test_top_level_commands_are_case_insensitive():
    bot = await _loaded_bot()
    try:
        assert bot.get_command("setup") is not None
        assert bot.get_command("Setup") is bot.get_command("setup")
        assert bot.get_command("AUTOMOD") is bot.get_command("automod")
        assert bot.get_command("HELP") is bot.get_command("help")
    finally:
        await _unload(bot)


async def test_subcommands_are_case_insensitive():
    bot = await _loaded_bot()
    try:
        assert bot.get_command("levels enable") is not None
        assert bot.get_command("Levels Enable") is bot.get_command("levels enable")
        # a nested group (automod words add) resolves at every depth
        assert bot.get_command("AutoMod Words Add") is bot.get_command("automod words add")
    finally:
        await _unload(bot)
