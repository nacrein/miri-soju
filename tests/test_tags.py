"""Tags: the create/edit/delete/use service contract (DB-backed) and the cog's
name validation (length + reserved words)."""

from __future__ import annotations

import pytest
from discord.ext import commands

from src.database.base import Base
from src.database.session import engine
from src.modules.tags import service
from src.modules.tags.cog import _clean_name


async def _schema() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# ── service contract ─────────────────────────────────────────────────────────

async def test_create_is_unique_per_guild_name():
    await _schema()
    guild = 710001
    assert await service.create(guild, "hi", "hello", 1) is True
    assert await service.create(guild, "hi", "again", 2) is False  # duplicate name
    tag = await service.get(guild, "hi")
    assert tag.content == "hello" and tag.author_id == 1


async def test_use_returns_content_and_counts_the_use():
    await _schema()
    guild = 710002
    await service.create(guild, "rule", "be nice", 1)
    assert await service.use(guild, "rule") == "be nice"
    assert await service.use(guild, "rule") == "be nice"
    assert (await service.get(guild, "rule")).uses == 2
    assert await service.use(guild, "missing") is None


async def test_edit_and_delete():
    await _schema()
    guild = 710003
    await service.create(guild, "x", "old", 1)
    assert await service.set_content(guild, "x", "new") is True
    assert (await service.get(guild, "x")).content == "new"
    assert await service.delete(guild, "x") is True
    assert await service.get(guild, "x") is None
    assert await service.delete(guild, "x") is False


# ── name validation ──────────────────────────────────────────────────────────

def test_clean_name_lowercases_and_trims():
    assert _clean_name("  HeLLo  ") == "hello"


def test_clean_name_rejects_reserved_and_overlong():
    with pytest.raises(commands.BadArgument):
        _clean_name("list")
    with pytest.raises(commands.BadArgument):
        _clean_name("a" * 101)
    with pytest.raises(commands.BadArgument):
        _clean_name("   ")
