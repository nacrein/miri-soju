"""Async engine and session factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from config.settings import get_settings

_settings = get_settings()

# Pool sizing applies to server databases (Postgres); SQLite ignores it.
_engine_kwargs: dict = {"pool_pre_ping": True, "echo": _settings.db_echo}
if not _settings.database_url.startswith("sqlite"):
    _engine_kwargs["pool_size"] = _settings.db_pool_size
    _engine_kwargs["max_overflow"] = _settings.db_max_overflow

engine = create_async_engine(_settings.database_url, **_engine_kwargs)

_session_factory = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    """Commits on success, rolls back on error, always closes."""
    session = _session_factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
