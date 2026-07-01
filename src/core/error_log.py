"""Persist and look up unhandled errors by their short code.

Lives in core because ``core/errors.py`` mints the codes. It imports the database
layer (infrastructure, not a feature module), so the "core never imports features"
rule still holds. Persistence is best-effort: error reporting must never itself error.
"""

from __future__ import annotations

import logging
import traceback as _traceback

from sqlalchemy import select

from src.database.models.errorlog import ErrorLog
from src.database.session import get_session

log = logging.getLogger(__name__)


async def record_error(
    code: str, context: str, exc: BaseException, *,
    guild_id: int | None = None, user_id: int | None = None,
) -> None:
    """Write an unhandled error so it can be looked up later. Never raises."""
    try:
        tb = "".join(_traceback.format_exception(type(exc), exc, exc.__traceback__))
        async with get_session() as session:
            session.add(ErrorLog(
                code=code,
                context=context[:200],
                exc_type=type(exc).__name__[:120],
                message=(str(exc) or "(no message)")[:1000],
                traceback=tb[-3500:],  # keep the tail, the most relevant frames
                guild_id=guild_id,
                user_id=user_id,
            ))
    except Exception:
        log.exception("could not persist error %s", code)


async def get_error(code: str) -> ErrorLog | None:
    """The most recent logged error for a code (codes are random, collisions unlikely)."""
    async with get_session() as session:
        stmt = select(ErrorLog).where(ErrorLog.code == code).order_by(ErrorLog.id.desc())
        return (await session.execute(stmt)).scalars().first()


async def list_recent_errors(limit: int = 50) -> list[ErrorLog]:
    """The most recent logged errors, newest first (staff dashboard view)."""
    async with get_session() as session:
        stmt = select(ErrorLog).order_by(ErrorLog.id.desc()).limit(limit)
        return list((await session.execute(stmt)).scalars().all())


async def count_errors_since(days: int) -> int:
    """How many errors were logged in the last ``days`` days."""
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import func

    since = datetime.now(UTC) - timedelta(days=days)
    async with get_session() as session:
        stmt = select(func.count()).select_from(ErrorLog).where(ErrorLog.created_at >= since)
        return int((await session.execute(stmt)).scalar_one())
