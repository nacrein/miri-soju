"""Cross-process config-cache invalidation over Postgres LISTEN/NOTIFY.

The bot serves per-guild config from in-process ``TTLCache``es (src/core/cache.py),
so a write made by *another* process — the dashboard — would otherwise stay invisible
to the running bot until the 300s TTL lapsed. To close that gap the writer publishes
the guild id on a Postgres ``NOTIFY`` channel and the bot ``LISTEN``s, dropping that
guild's entry from every registered cache the moment it hears.

Postgres-only: on SQLite (tests / local dev) both ends are no-ops, so nothing breaks
and the single-process bot keeps relying on its own post-write cache invalidation.
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import func, select

from config.settings import get_settings
from src.core import cache
from src.database.session import get_session

log = logging.getLogger(__name__)

CHANNEL = "miri_cache_invalidate"


def _is_postgres() -> bool:
    return get_settings().database_url.startswith(("postgres", "postgresql"))


async def publish_guild_changed(guild_id: int) -> None:
    """Tell other processes to drop their cached config for ``guild_id``.

    No-op unless the backing store is Postgres. Never raises into the caller: a
    failed fan-out must not fail the write that triggered it."""
    if not _is_postgres():
        return
    try:
        async with get_session() as session:
            await session.execute(select(func.pg_notify(CHANNEL, str(guild_id))))
    except Exception:  # pragma: no cover - best-effort fan-out
        log.exception("cache-invalidate publish failed for guild %s", guild_id)


async def run_listener() -> None:
    """Drop the named guild from every cache whenever an invalidation notice arrives.

    Runs until cancelled, reconnecting with capped backoff if the connection drops.
    No-op on non-Postgres backends (returns immediately)."""
    if not _is_postgres():
        return
    import asyncpg  # local import: only needed when actually listening

    # SQLAlchemy DSNs carry the driver (postgresql+asyncpg://...); asyncpg wants it bare.
    dsn = get_settings().database_url.replace("+asyncpg", "")

    def _on_notify(_conn, _pid, _channel, payload: str) -> None:
        try:
            cache.invalidate_guild(int(payload))
        except (TypeError, ValueError):
            log.warning("ignoring bad cache-invalidate payload: %r", payload)

    backoff = 1.0
    while True:
        conn = None
        try:
            conn = await asyncpg.connect(dsn)
            await conn.add_listener(CHANNEL, _on_notify)
            log.info("listening for cross-process cache invalidation on %r", CHANNEL)
            backoff = 1.0
            while True:  # keep the connection (and its reader) alive
                await asyncio.sleep(3600)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("cache-invalidate listener dropped; reconnecting in %.0fs", backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30.0)
        finally:
            if conn is not None:
                try:
                    await conn.close()
                except Exception:  # pragma: no cover
                    pass
