"""Cross-server message counter: bump upserts+increments per (guild, user), and
by_user lists a user's guilds busiest-first (and only that user's)."""

from __future__ import annotations

import src.database.models  # noqa: F401 — registers every table on Base.metadata
from src.database.base import Base
from src.database.session import engine, get_session
from src.modules.msgcounter.repository import MsgCountRepository


async def _schema() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def test_bump_creates_then_increments():
    await _schema()
    guild, user = 111, 222
    # Separate sessions, mirroring the per-flush write path.
    async with get_session() as s:
        await MsgCountRepository(s).bump(guild, user, 1)
    async with get_session() as s:
        await MsgCountRepository(s).bump(guild, user, 3)
    async with get_session() as s:
        rows = await MsgCountRepository(s).by_user(user)
    assert rows == [(guild, 4)]


async def test_by_user_lists_shared_guilds_busiest_first():
    await _schema()
    user = 900_001
    async with get_session() as s:
        repo = MsgCountRepository(s)
        await repo.bump(10, user, 5)
        await repo.bump(20, user, 50)
        await repo.bump(30, user, 25)
        await repo.bump(40, 999_999, 100)  # a different user — must not leak in
    async with get_session() as s:
        rows = await MsgCountRepository(s).by_user(user)
    assert [g for g, _ in rows] == [20, 30, 10]  # descending by count
    assert dict(rows) == {20: 50, 30: 25, 10: 5}


async def test_by_user_empty_for_unknown_user():
    await _schema()
    async with get_session() as s:
        assert await MsgCountRepository(s).by_user(123_456_789) == []
