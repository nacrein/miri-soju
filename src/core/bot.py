"""The Bot subclass: intents, cog auto-discovery, startup hooks."""

from __future__ import annotations

import asyncio
import logging
import os
import pkgutil
from importlib import import_module

import discord
from discord.ext import commands

from config.settings import get_settings
from src.core import blacklist, cache_sync
from src.core.embeds import apply_author
from src.core.errors import BlacklistedError, setup_error_handling

try:  # the dict discord.py uses for case-insensitive command lookup
    from discord.ext.commands.core import _CaseInsensitiveDict
except Exception:  # pragma: no cover - fallback if the private name ever moves
    class _CaseInsensitiveDict(dict):
        def __contains__(self, k):
            return super().__contains__(k.casefold())

        def __delitem__(self, k):
            return super().__delitem__(k.casefold())

        def __getitem__(self, k):
            return super().__getitem__(k.casefold())

        def get(self, k, default=None):
            return super().get(k.casefold(), default)

        def pop(self, k, default=None):
            return super().pop(k.casefold(), default)

        def __setitem__(self, k, v):
            super().__setitem__(k.casefold(), v)

log = logging.getLogger(__name__)

_MODULES_PACKAGE = "src.modules"

# The status Miri wears in the member list. Hostess vibe; edit the one line to taste.
_PRESENCE = discord.Activity(type=discord.ActivityType.listening, name="orders")


def _make_case_insensitive(command: commands.Command) -> None:
    """Make a group (and its subgroups) match subcommands case-insensitively.

    ``case_insensitive=True`` on the Bot only covers top-level commands; each Group
    keeps its own lookup table. Convert them so ``,Levels Enable`` resolves exactly
    like ``,levels enable`` at every depth — phone auto-capitalisation included."""
    if not isinstance(command, commands.Group) or command.case_insensitive:
        return
    command.case_insensitive = True
    existing = command.all_commands
    command.all_commands = _CaseInsensitiveDict()
    for key, sub in existing.items():
        command.all_commands[key] = sub  # re-store names + aliases, now casefolded
    for sub in set(existing.values()):
        _make_case_insensitive(sub)

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
            case_insensitive=True,  # ,Setup == ,setup (top-level; groups handled in add_command)
        )
        # A blacklisted user is blocked from every command, silently.
        self.add_check(self._not_blacklisted)

    async def _not_blacklisted(self, ctx: commands.Context) -> bool:
        """Global check: bot-blacklisted users can run nothing. The owner is exempt so
        a bad blacklist can always be lifted."""
        if await self.is_owner(ctx.author):
            return True
        if await blacklist.is_blacklisted(ctx.author.id, "bot"):
            raise BlacklistedError()
        return True

    def add_command(self, command: commands.Command) -> None:
        # Every group becomes case-insensitive as it's registered, so subcommands
        # match regardless of capitalisation too (not just top-level commands).
        _make_case_insensitive(command)
        super().add_command(command)

    async def get_context(self, origin, *, cls=BotContext):
        # Route both prefix messages and hybrid/slash interactions through the
        # author-stamping Context above.
        return await super().get_context(origin, cls=cls)

    async def setup_hook(self) -> None:
        setup_error_handling(self)
        await self._load_jishaku()
        await self._load_all_cogs()
        await self._sync_app_commands()
        # Hear config writes made by the dashboard (a separate process) and drop the
        # affected guild from our in-process caches at once. No-op on SQLite.
        self._cache_listener = asyncio.create_task(cache_sync.run_listener())

    async def close(self) -> None:
        listener = getattr(self, "_cache_listener", None)
        if listener is not None:
            listener.cancel()
        await super().close()

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

    async def _load_jishaku(self) -> None:
        """Load our themed jishaku (an on-brand ,jsk overview over stock jishaku).

        Falls back to stock jishaku if the themed cog fails to load, so a jishaku
        API change can degrade the theming but never block startup. Loaded here,
        before _load_all_cogs, so the auto-discovery walker just sees it as already
        loaded (it swallows ExtensionAlreadyLoaded)."""
        try:
            await self.load_extension("src.modules.owner.jsk")
            return
        except Exception:
            log.exception("Themed jsk failed to load; falling back to stock jishaku")
        try:
            await self.load_extension("jishaku")
        except Exception:
            log.exception("Stock jishaku also failed to load; dev tools unavailable")

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
        await self.change_presence(activity=_PRESENCE)
        log.info("Logged in as %s (id: %s)", self.user, self.user.id if self.user else "?")
