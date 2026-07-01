"""Reads/writes for the command-usage log.

One writer (``record``, called on the hot path from the completion listener) and a
handful of aggregate reads the dashboard's staff view consumes. Date bucketing uses
``func.date`` so the same query works on SQLite (dev) and Postgres (prod)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models.command_usage import CommandUsage


class AnalyticsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record(self, command: str, user_id: int, guild_id: int | None) -> None:
        """Append one invocation. Called once per completed command."""
        self.session.add(
            CommandUsage(command=command[:100], user_id=user_id, guild_id=guild_id)
        )

    async def totals(self) -> dict:
        """Headline counters: total invocations, distinct users, distinct commands."""
        stmt = select(
            func.count(CommandUsage.id),
            func.count(func.distinct(CommandUsage.user_id)),
            func.count(func.distinct(CommandUsage.command)),
        )
        total, users, commands = (await self.session.execute(stmt)).one()
        return {
            "invocations": int(total),
            "unique_users": int(users),
            "distinct_commands": int(commands),
        }

    async def top_commands(self, limit: int = 15, days: int | None = None) -> list[tuple[str, int]]:
        """Most-used commands as [(command, count), ...], optionally within a window."""
        count = func.count(CommandUsage.id)
        stmt = select(CommandUsage.command, count.label("n"))
        if days is not None:
            since = datetime.now(UTC) - timedelta(days=days)
            stmt = stmt.where(CommandUsage.created_at >= since)
        stmt = stmt.group_by(CommandUsage.command).order_by(count.desc()).limit(limit)
        return [(c, int(n)) for c, n in (await self.session.execute(stmt)).all()]

    async def usage_by_day(self, days: int = 14) -> list[tuple[str, int]]:
        """Invocations per calendar day for the last ``days`` days: [(YYYY-MM-DD, count)]."""
        since = datetime.now(UTC) - timedelta(days=days)
        day = func.date(CommandUsage.created_at)
        stmt = (
            select(day.label("day"), func.count(CommandUsage.id))
            .where(CommandUsage.created_at >= since)
            .group_by(day)
            .order_by(day)
        )
        return [(str(d), int(n)) for d, n in (await self.session.execute(stmt)).all()]

    async def usage_by_hour(self) -> list[tuple[int, int]]:
        """Invocations bucketed by hour-of-day (0..23) across all history.

        ``extract('hour', ...)`` is dialect-portable — EXTRACT on Postgres,
        STRFTIME on SQLite — so this reads the same on dev and prod."""
        hour = extract("hour", CommandUsage.created_at)
        stmt = select(hour.label("h"), func.count(CommandUsage.id)).group_by(hour).order_by(hour)
        return [(int(h), int(n)) for h, n in (await self.session.execute(stmt)).all()]
