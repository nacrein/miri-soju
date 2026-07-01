"""Bot-staff-only analytics — command usage, moderation, and error logs.

Unlike every other router here (which is *guild*-scoped via ``require_guild``),
these endpoints are *bot*-scoped: they read global, cross-guild aggregates and are
gated by ``require_staff`` (the bot's owner/staff ids). Read-only — nothing here
mutates state. Each endpoint reuses the modules' existing repositories, matching
the leveling-router pattern.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from dashboard.deps import require_staff
from dashboard.schemas import (
    CommandAnalyticsOut,
    CommandTotalsOut,
    ErrorAnalyticsOut,
    ErrorRowOut,
    ModActionOut,
    ModerationAnalyticsOut,
    StaffSummaryOut,
    TopCommandOut,
    UsageDayOut,
    UsageHourOut,
)
from src.core import error_log
from src.database.session import get_session
from src.modules.analytics.repository import AnalyticsRepository
from src.modules.moderation.repository import ModerationRepository

router = APIRouter(prefix="/staff", tags=["staff"], dependencies=[Depends(require_staff)])


def _iso(dt) -> str:
    """Serialize a stored datetime; tolerate SQLite's naive values."""
    return dt.isoformat() if dt is not None else ""


@router.get("/summary", response_model=StaffSummaryOut)
async def summary() -> StaffSummaryOut:
    """The headline counters shown across the top of the staff dashboard."""
    async with get_session() as session:
        cmd_totals = await AnalyticsRepository(session).totals()
        mod_cases = await ModerationRepository(session).total_cases()
    errors_24h = await error_log.count_errors_since(1)
    errors_total = await error_log.count_errors_since(3650)  # ~all
    return StaffSummaryOut(
        commands=CommandTotalsOut(**cmd_totals),
        mod_cases=mod_cases,
        errors_24h=errors_24h,
        errors_total=errors_total,
    )


@router.get("/commands", response_model=CommandAnalyticsOut)
async def commands() -> CommandAnalyticsOut:
    """Command-usage analytics: totals, all-time + 30-day leaders, daily volume."""
    async with get_session() as session:
        repo = AnalyticsRepository(session)
        totals = await repo.totals()
        top = await repo.top_commands(limit=15)
        top_30d = await repo.top_commands(limit=15, days=30)
        by_day = await repo.usage_by_day(days=14)
        by_hour = await repo.usage_by_hour()
    return CommandAnalyticsOut(
        totals=CommandTotalsOut(**totals),
        top=[TopCommandOut(command=c, count=n) for c, n in top],
        top_30d=[TopCommandOut(command=c, count=n) for c, n in top_30d],
        by_day=[UsageDayOut(day=d, count=n) for d, n in by_day],
        by_hour=[UsageHourOut(hour=h, count=n) for h, n in by_hour],
    )


@router.get("/moderation", response_model=ModerationAnalyticsOut)
async def moderation() -> ModerationAnalyticsOut:
    """Moderation-action analytics across all guilds (from the case log)."""
    async with get_session() as session:
        repo = ModerationRepository(session)
        total = await repo.total_cases()
        breakdown = await repo.action_breakdown()
        by_day = await repo.actions_by_day(days=14)
    return ModerationAnalyticsOut(
        total_cases=total,
        breakdown=[ModActionOut(kind=k, count=n) for k, n in breakdown],
        by_day=[UsageDayOut(day=d, count=n) for d, n in by_day],
    )


@router.get("/errors", response_model=ErrorAnalyticsOut)
async def errors() -> ErrorAnalyticsOut:
    """Recent unhandled errors (the same rows ``,staff error <code>`` reads)."""
    errors_24h = await error_log.count_errors_since(1)
    errors_total = await error_log.count_errors_since(3650)
    rows = await error_log.list_recent_errors(limit=50)
    return ErrorAnalyticsOut(
        errors_24h=errors_24h,
        errors_total=errors_total,
        recent=[
            ErrorRowOut(
                code=e.code,
                context=e.context,
                exc_type=e.exc_type,
                message=e.message,
                guild_id=str(e.guild_id) if e.guild_id else None,
                user_id=str(e.user_id) if e.user_id else None,
                created_at=_iso(e.created_at),
            )
            for e in rows
        ],
    )
