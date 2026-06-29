"""The error-log round-trip: an unhandled error is persisted and looked up by code.

This is what powers ,staff error <code>. Uses the test SQLite DB."""

from __future__ import annotations

from src.core import error_log
from src.database.base import Base
from src.database.session import engine


async def _schema() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def test_record_then_lookup_by_code():
    await _schema()
    try:
        raise ValueError("boom in a command")
    except ValueError as exc:
        await error_log.record_error("ABC123", "command 'vm enable'", exc, guild_id=5, user_id=6)

    rec = await error_log.get_error("ABC123")
    assert rec is not None
    assert rec.code == "ABC123"
    assert rec.context == "command 'vm enable'"
    assert rec.exc_type == "ValueError"
    assert rec.message == "boom in a command"
    assert rec.guild_id == 5 and rec.user_id == 6
    assert rec.traceback and "ValueError" in rec.traceback


async def test_unknown_code_returns_none():
    await _schema()
    assert await error_log.get_error("ZZZZZZ") is None


async def test_record_error_swallows_failures():
    # A None exception or odd input must not raise out of the error reporter.
    await _schema()
    await error_log.record_error("NIL000", "context", Exception(), guild_id=None, user_id=None)
    rec = await error_log.get_error("NIL000")
    assert rec is not None and rec.message == "(no message)"
