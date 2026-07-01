"""Blacklist core: the bot-wide and economy-only gates are independent, cached,
and idempotent to lift."""

from __future__ import annotations

import src.database.models  # noqa: F401 — registers every table on Base.metadata
from src.core import blacklist
from src.database.base import Base
from src.database.session import engine


async def _schema() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def test_scopes_are_independent():
    await _schema()
    uid = 800_000_001
    await blacklist.add(uid, "economy", "farming alts", added_by=1)
    assert await blacklist.is_blacklisted(uid, "economy") is True
    assert await blacklist.is_blacklisted(uid, "bot") is False


async def test_user_can_hold_both_scopes():
    await _schema()
    uid = 800_000_002
    await blacklist.add(uid, "bot", None, added_by=1)
    await blacklist.add(uid, "economy", None, added_by=1)
    assert await blacklist.is_blacklisted(uid, "bot") is True
    assert await blacklist.is_blacklisted(uid, "economy") is True


async def test_remove_is_scoped_and_idempotent():
    await _schema()
    uid = 800_000_003
    await blacklist.add(uid, "bot", None, added_by=1)
    assert await blacklist.remove(uid, "bot") is True
    assert await blacklist.is_blacklisted(uid, "bot") is False
    # Removing again (or something never added) reports False, doesn't raise.
    assert await blacklist.remove(uid, "bot") is False
    assert await blacklist.remove(999_999, "economy") is False
