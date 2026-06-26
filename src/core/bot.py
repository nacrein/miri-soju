"""The Bot subclass: intents, cog auto-discovery, startup hooks."""

from __future__ import annotations

import logging
import os
import pkgutil
from importlib import import_module

import discord
from discord.ext import commands

from config.settings import get_settings
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


class Bot(commands.Bot):
    def __init__(self) -> None:
        owner_id = get_settings().owner_id
        super().__init__(
            command_prefix=commands.when_mentioned_or(","),
            intents=_intents(),
            help_command=None,
            owner_id=owner_id,  # if None, discord.py derives it from the app
        )

    async def _reconcile_economy(self) -> None:
        """Refund any game stakes stranded by a previous restart. Non-fatal."""
        try:
            from src.modules.economy.service import reconcile_stranded_escrows

            count = await reconcile_stranded_escrows()
            if count:
                log.info("Reconciled %d stranded game escrow(s) on startup", count)
        except Exception:
            log.exception("Economy escrow reconciliation failed (continuing)")

    async def setup_hook(self) -> None:
        setup_error_handling(self)
        await self.load_extension("jishaku")
        await self._load_all_cogs()
        await self._reconcile_economy()

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
