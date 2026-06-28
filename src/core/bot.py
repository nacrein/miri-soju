"""The Bot subclass: intents, cog auto-discovery, startup hooks."""

from __future__ import annotations

import logging
import os
import pkgutil
from importlib import import_module

import discord
from discord.ext import commands

from config.settings import get_settings
from src.core.embeds import apply_author
from src.core.errors import setup_error_handling

log = logging.getLogger(__name__)

_MODULES_PACKAGE = "src.modules"

os.environ.setdefault("JISHAKU_NO_UNDERSCORE", "true")
os.environ.setdefault("JISHAKU_NO_DM_TRACEBACK", "true")
os.environ.setdefault("JISHAKU_HIDE", "true")


def _intents() -> discord.Intents:
    intents = discord.Intents.default()
    intents.message_content = True  # privileged: also enable in the dev portal
    intents.members = True          # privileged: also enable in the dev portal
    return intents


async def _get_prefix(bot: commands.Bot, message: discord.Message) -> list[str]:
    """Resolve the invocation prefixes: the bot mention, plus the guild's
    configured prefix (cached) or the ',' default. DMs always use the default."""
    prefix = ","
    if message.guild is not None:
        from src.modules.prefix.service import get_prefix

        prefix = await get_prefix(message.guild.id)
    return commands.when_mentioned_or(prefix)(bot, message)


class BotContext(commands.Context):
    """Context whose ``send`` gives every embed the invoker's author row, unless
    the embed already set one. This is how the house style reaches every command
    without each call site opting in: one hook instead of a hundred."""

    async def send(self, content: str | None = None, **kwargs):  # type: ignore[override]
        if (embed := kwargs.get("embed")) is not None:
            apply_author(embed, self.author)
        for embed in kwargs.get("embeds") or ():
            apply_author(embed, self.author)
        return await super().send(content, **kwargs)


class Bot(commands.Bot):
    def __init__(self) -> None:
        owner_id = get_settings().owner_id
        super().__init__(
            command_prefix=_get_prefix,
            intents=_intents(),
            help_command=None,
            owner_id=owner_id,  # if None, discord.py derives it from the app
        )

    async def get_context(self, origin, *, cls=BotContext):
        # Route both prefix messages and hybrid/slash interactions through the
        # author-stamping Context above.
        return await super().get_context(origin, cls=cls)

    async def setup_hook(self) -> None:
        setup_error_handling(self)
        await self.load_extension("jishaku")
        await self._load_all_cogs()
        await self._sync_app_commands()

    async def _sync_app_commands(self) -> None:
        """Push hybrid/app commands to Discord. Hybrid commands are added to the
        tree as each cog loads, but Discord only learns about them after a sync —
        without this, slash commands never appear (prefix commands need no sync).

        With DEV_GUILD_ID set we copy the global commands into that one guild and
        sync there: instant, ideal while developing. Global registration (visible
        everywhere, up to ~1h propagation) stays manual via `jsk sync` to avoid
        the per-restart global sync rate limit."""
        guild_id = get_settings().dev_guild_id
        if guild_id is None:
            log.info("DEV_GUILD_ID unset; run `jsk sync` to register slash commands globally")
            return
        guild = discord.Object(id=guild_id)
        self.tree.copy_global_to(guild=guild)
        synced = await self.tree.sync(guild=guild)
        log.info("Synced %d app command(s) to dev guild %s", len(synced), guild_id)

    async def _load_all_cogs(self) -> None:
        """Load every submodule of src.modules that exposes setup()."""
        package = import_module(_MODULES_PACKAGE)
        loaded = 0
        for module_info in pkgutil.walk_packages(package.__path__, f"{_MODULES_PACKAGE}."):
            if module_info.ispkg:
                continue
            name = module_info.name
            try:
                target = import_module(name)
            except Exception:
                log.exception("Failed to import %s", name)
                continue
            if not hasattr(target, "setup"):
                continue
            try:
                await self.load_extension(name)
                loaded += 1
            except commands.ExtensionAlreadyLoaded:
                pass
            except Exception:
                log.exception("Failed to load cog %s", name)
        log.info("Loaded %d cog(s)", loaded)

    async def on_ready(self) -> None:
        log.info("Logged in as %s (id: %s)", self.user, self.user.id if self.user else "?")
