"""Blacklist core: the bot-wide gate is cached, upserts its reason, and is
idempotent to lift. Only the 'bot' scope is valid (see chk_blacklist_scope)."""

from __future__ import annotations

import src.database.models  # noqa: F401 — registers every table on Base.metadata
from src.core import blacklist
from src.database.base import Base
from src.database.session import engine


async def _schema() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def test_add_then_blacklisted():
    await _schema()
    uid = 800_000_001
    assert await blacklist.is_blacklisted(uid, "bot") is False
    await blacklist.add(uid, "bot", "raiding", added_by=1)
    assert await blacklist.is_blacklisted(uid, "bot") is True


async def test_add_upserts_and_refreshes_reason():
    await _schema()
    uid = 800_000_002
    await blacklist.add(uid, "bot", None, added_by=1)
    await blacklist.add(uid, "bot", "updated reason", added_by=1)
    assert await blacklist.is_blacklisted(uid, "bot") is True
    rows = await blacklist.list_scope("bot")
    assert any(r.discord_id == uid and r.reason == "updated reason" for r in rows)


async def test_remove_is_idempotent():
    await _schema()
    uid = 800_000_003
    await blacklist.add(uid, "bot", None, added_by=1)
    assert await blacklist.remove(uid, "bot") is True
    assert await blacklist.is_blacklisted(uid, "bot") is False
    # Removing again (or someone never added) reports False, doesn't raise.
    assert await blacklist.remove(uid, "bot") is False
    assert await blacklist.remove(999_999, "bot") is False
