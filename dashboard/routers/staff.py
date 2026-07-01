"""Bot-staff-only analytics — economy, command usage, and error logs.

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
    EconomyAnalyticsOut,
    EconomyTotalsOut,
    ErrorAnalyticsOut,
    ErrorRowOut,
    LedgerKindOut,
    LedgerRowOut,
    StaffSummaryOut,
    TopCommandOut,
    TopPlayerOut,
    UsageDayOut,
)
from src.core import error_log
from src.database.session import get_session
from src.modules.analytics.repository import AnalyticsRepository
from src.modules.economy.repository import EconomyRepository

router = APIRouter(prefix="/staff", tags=["staff"], dependencies=[Depends(require_staff)])


def _iso(dt) -> str:
    """Serialize a stored datetime; tolerate SQLite's naive values."""
    return dt.isoformat() if dt is not None else ""


@router.get("/summary", response_model=StaffSummaryOut)
async def summary() -> StaffSummaryOut:
    """The headline counters shown across the top of the staff dashboard."""
    async with get_session() as session:
        econ = EconomyRepository(session)
        totals = await econ.economy_totals()
        ledger_rows = await econ.total_transactions()
        cmd_totals = await AnalyticsRepository(session).totals()
    errors_24h = await error_log.count_errors_since(1)
    errors_total = await error_log.count_errors_since(3650)  # ~all
    return StaffSummaryOut(
        economy=EconomyTotalsOut(**totals),
        ledger_rows=ledger_rows,
        commands=CommandTotalsOut(**cmd_totals),
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
    return CommandAnalyticsOut(
        totals=CommandTotalsOut(**totals),
        top=[TopCommandOut(command=c, count=n) for c, n in top],
        top_30d=[TopCommandOut(command=c, count=n) for c, n in top_30d],
        by_day=[UsageDayOut(day=d, count=n) for d, n in by_day],
    )


@router.get("/economy", response_model=EconomyAnalyticsOut)
async def economy() -> EconomyAnalyticsOut:
    """Economy analytics: circulation, per-kind ledger flow, richest players, feed."""
    async with get_session() as session:
        repo = EconomyRepository(session)
        totals = await repo.economy_totals()
        ledger_rows = await repo.total_transactions()
        breakdown = await repo.transaction_breakdown()
        top_net = await repo.top_by_net_worth(limit=10)
        top_wallet = await repo.top_by_wallet(limit=10)
        recent = await repo.recent_transactions_all(limit=25)
        recent_rows = [
            LedgerRowOut(
                user_id=str(t.discord_id),
                kind=t.kind,
                amount=t.amount,
                balance_after=t.balance_after,
                created_at=_iso(t.created_at),
            )
            for t in recent
        ]
    return EconomyAnalyticsOut(
        totals=EconomyTotalsOut(**totals),
        ledger_rows=ledger_rows,
        breakdown=[LedgerKindOut(kind=k, count=c, net=n) for k, c, n in breakdown],
        top_net_worth=[
            TopPlayerOut(
                user_id=str(p.discord_id),
                net_worth=p.wallet + p.vault,
                wallet=p.wallet,
                vault=p.vault,
            )
            for p in top_net
        ],
        top_wallet=[
            TopPlayerOut(
                user_id=str(p.discord_id),
                net_worth=p.wallet + p.vault,
                wallet=p.wallet,
                vault=p.vault,
            )
            for p in top_wallet
        ],
        recent=recent_rows,
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
