"""Tests for server-log config caching and Discord-free channel resolution.

Two layers:
* ``resolve_log_channel`` over the test SQLite DB — toggles gate the channel id.
* The ``_NO_CONFIG`` negative-cache — an unconfigured guild is queried once, then
  served from cache (no DB round-trip per logged event).
"""

from __future__ import annotations

from src.database.base import Base
from src.database.session import engine
from src.modules.serverlog import service


async def _schema() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# ── channel resolution (DB-backed) ────────────────────────────────────────────

async def test_resolve_returns_none_for_unconfigured_guild():
    await _schema()
    service._config_cache.clear()
    assert await service.resolve_log_channel(510001, "join") is None


async def test_resolve_returns_channel_only_when_category_toggled_on():
    await _schema()
    service._config_cache.clear()
    guild = 510002
    await service.set_log_channel(guild, 42)
    # Joins default on; an off category resolves to None even with a channel set.
    await service.set_event_flag(guild, "log_joins", True)
    await service.set_event_flag(guild, "log_leaves", False)
    assert await service.resolve_log_channel(guild, "join") == 42
    assert await service.resolve_log_channel(guild, "leave") is None


async def test_resolve_returns_none_after_logging_disabled():
    await _schema()
    service._config_cache.clear()
    guild = 510003
    await service.set_log_channel(guild, 7)
    await service.set_event_flag(guild, "log_joins", True)
    assert await service.resolve_log_channel(guild, "join") == 7
    await service.disable_logging(guild)
    assert await service.resolve_log_channel(guild, "join") is None


# ── negative cache (no re-query for unconfigured guilds) ──────────────────────

async def test_missing_config_is_negative_cached(monkeypatch):
    await _schema()
    service._config_cache.clear()
    guild = 510004

    calls = {"n": 0}
    real_load = service.GuildConfigRepository.get

    async def counting_get(self, gid):
        calls["n"] += 1
        return await real_load(self, gid)

    monkeypatch.setattr(service.GuildConfigRepository, "get", counting_get)

    # First event hits the DB and caches the miss as the sentinel.
    assert await service.resolve_log_channel(guild, "join") is None
    # Subsequent events for the same unconfigured guild must NOT re-query.
    assert await service.resolve_log_channel(guild, "leave") is None
    assert await service.resolve_log_channel(guild, "msg_delete") is None
    assert calls["n"] == 1


async def test_write_invalidates_negative_cache(monkeypatch):
    await _schema()
    service._config_cache.clear()
    guild = 510005
    # Prime the negative cache.
    assert await service.resolve_log_channel(guild, "join") is None
    # A config write invalidates it, so the next read reflects the new channel.
    await service.set_log_channel(guild, 99)
    await service.set_event_flag(guild, "log_joins", True)
    assert await service.resolve_log_channel(guild, "join") == 99
