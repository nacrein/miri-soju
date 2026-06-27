"""Whole-repo smoke test.

These do not prove behavioral correctness — they prove the repo *loads*: every
module imports, every model builds a table, and every cog the bot auto-discovers
registers cleanly (which is where discord.py validates command signatures,
duplicate names, and bad decorators). For a codebase landed "applied, untested",
this catches the large class of bugs that never even reach runtime.
"""

from __future__ import annotations

import importlib
import pkgutil

from discord.ext import commands

import src.database.models  # noqa: F401 — registers every table on Base.metadata
from src.database.base import Base
from src.database.session import engine


async def _create_schema() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def _walk(package_name: str):
    """Yield the package and every submodule name under it."""
    package = importlib.import_module(package_name)
    yield package_name
    for info in pkgutil.walk_packages(package.__path__, f"{package_name}."):
        yield info.name


# ── Tier 1: everything imports ──────────────────────────────────────────────

def test_all_modules_import():
    failures: dict[str, str] = {}
    for name in _walk("src"):
        try:
            importlib.import_module(name)
        except Exception as e:  # noqa: BLE001 — we want to report *every* failure
            failures[name] = f"{type(e).__name__}: {e}"
    assert not failures, "Modules failed to import:\n" + "\n".join(
        f"  {k}: {v}" for k, v in sorted(failures.items())
    )


# ── Tier 3: the schema builds ───────────────────────────────────────────────

async def test_schema_creates():
    await _create_schema()
    assert Base.metadata.tables, "No tables registered on Base.metadata"


# ── Tier 2: every cog loads (the important one) ─────────────────────────────

async def test_all_cogs_load():
    from src.core.bot import Bot

    await _create_schema()
    bot = Bot()
    loaded = 0
    errors: dict[str, str] = {}

    package = importlib.import_module("src.modules")
    for info in pkgutil.walk_packages(package.__path__, "src.modules."):
        if info.ispkg:
            continue
        module = importlib.import_module(info.name)
        if not hasattr(module, "setup"):
            continue
        try:
            await bot.load_extension(info.name)
            loaded += 1
        except commands.ExtensionAlreadyLoaded:
            pass
        except Exception as e:  # noqa: BLE001
            errors[info.name] = f"{type(e).__name__}: {e}"

    # Unload to cancel any background task loops a cog started in __init__.
    for ext in list(bot.extensions):
        await bot.unload_extension(ext)

    assert not errors, "Cogs failed to load:\n" + "\n".join(
        f"  {k}: {v}" for k, v in sorted(errors.items())
    )
    assert loaded > 0, "No cogs were discovered or loaded"
