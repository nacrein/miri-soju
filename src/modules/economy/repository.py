"""Economy data access. Provides the row-locked fetch that prevents races."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models.player import Player


class EconomyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, discord_id: int) -> Player | None:
        return await self.session.get(Player, discord_id)

    async def get_or_create(self, discord_id: int) -> Player:
        """Ensure a player row exists. Atomic UPSERT on Postgres; two-step on SQLite."""
        from src.modules.economy.config import VAULT_BASE_CAPACITY

        if self.session.bind.dialect.name == "postgresql":
            # Single atomic statement: insert, or do nothing if the row exists.
            stmt = (
                pg_insert(Player)
                .values(discord_id=discord_id, vault_capacity=VAULT_BASE_CAPACITY)
                .on_conflict_do_nothing(index_elements=["discord_id"])
            )
            await self.session.execute(stmt)
            return await self.get(discord_id)  # type: ignore[return-value]

        # Portable fallback (SQLite test harness).
        player = await self.get(discord_id)
        if player is None:
            player = Player(discord_id=discord_id, vault_capacity=VAULT_BASE_CAPACITY)
            self.session.add(player)
            await self.session.flush()
        return player

    async def get_for_update(self, discord_id: int) -> Player | None:
        """Fetch the row with a lock so concurrent mutations queue, not race."""
        stmt = select(Player).where(Player.discord_id == discord_id).with_for_update()
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_or_create_for_update(self, discord_id: int) -> Player:
        player = await self.get_for_update(discord_id)
        if player is None:
            await self.get_or_create(discord_id)
            player = await self.get_for_update(discord_id)
        return player  # type: ignore[return-value]

    async def net_worth_rank(self, discord_id: int) -> int | None:
        """1-based rank by net worth (1 = richest). None if the player is absent."""
        from sqlalchemy import func

        me = await self.get(discord_id)
        if me is None:
            return None
        my_worth = me.wallet + me.vault
        stmt = select(func.count()).select_from(Player).where(
            (Player.wallet + Player.vault) > my_worth
        )
        result = await self.session.execute(stmt)
        return int(result.scalar_one()) + 1

    async def top_by_net_worth(self, limit: int = 10) -> list[Player]:
        stmt = (
            select(Player)
            .order_by((Player.wallet + Player.vault).desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def top_by_wallet(self, limit: int = 10) -> list[Player]:
        stmt = select(Player).order_by(Player.wallet.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def top_by_generator(self, limit: int = 10) -> list[Player]:
        stmt = (
            select(Player)
            .where(Player.generator_tier > 0)
            .order_by(Player.generator_tier.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def economy_totals(self) -> dict:
        """Server-wide aggregate for staff: circulation, holdings, player count."""
        from sqlalchemy import func

        stmt = select(
            func.count(Player.discord_id),
            func.coalesce(func.sum(Player.wallet), 0),
            func.coalesce(func.sum(Player.vault), 0),
        )
        count, wallet_sum, vault_sum = (await self.session.execute(stmt)).one()
        return {
            "players": int(count),
            "wallet_total": int(wallet_sum),
            "vault_total": int(vault_sum),
            "circulation": int(wallet_sum) + int(vault_sum),
        }


    async def recent_transactions(self, discord_id: int, limit: int = 15, offset: int = 0):
        from src.database.models.transaction import Transaction

        stmt = (
            select(Transaction)
            .where(Transaction.discord_id == discord_id)
            .order_by(Transaction.created_at.desc(), Transaction.id.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def transaction_count(self, discord_id: int) -> int:
        from sqlalchemy import func

        from src.database.models.transaction import Transaction

        stmt = select(func.count()).select_from(Transaction).where(
            Transaction.discord_id == discord_id
        )
        result = await self.session.execute(stmt)
        return int(result.scalar_one())

    # ── staff-wide ledger aggregates (dashboard analytics) ───────────────────

    async def total_transactions(self) -> int:
        """Count of every ledger row ever written (staff view)."""
        from sqlalchemy import func

        from src.database.models.transaction import Transaction

        stmt = select(func.count()).select_from(Transaction)
        return int((await self.session.execute(stmt)).scalar_one())

    async def transaction_breakdown(self) -> list[tuple[str, int, int]]:
        """Per-kind [(kind, count, net_amount), ...], busiest kinds first.

        ``net_amount`` is the signed sum, so faucets read positive and sinks
        negative — a quick read on where bits enter and leave the economy."""
        from sqlalchemy import func

        from src.database.models.transaction import Transaction

        stmt = (
            select(
                Transaction.kind,
                func.count(Transaction.id),
                func.coalesce(func.sum(Transaction.amount), 0),
            )
            .group_by(Transaction.kind)
            .order_by(func.count(Transaction.id).desc())
        )
        rows = (await self.session.execute(stmt)).all()
        return [(k, int(c), int(s)) for k, c, s in rows]

    async def recent_transactions_all(self, limit: int = 25):
        """Newest ledger rows across every user — a live economy feed for staff."""
        from src.database.models.transaction import Transaction

        stmt = (
            select(Transaction)
            .order_by(Transaction.created_at.desc(), Transaction.id.desc())
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def game_session_resolved(self, session_id: str) -> bool:
        """True if this game session already has a resolution row.

        A resolution is any of game_payout / game_forfeit / game_refund. Used to
        make payout/forfeit idempotent against the concurrent component clicks
        discord.py dispatches as separate tasks (and against on_timeout racing a
        final click)."""
        from sqlalchemy import func

        from src.database.models.transaction import Transaction

        stmt = select(func.count()).select_from(Transaction).where(
            Transaction.game_session_id == session_id,
            Transaction.kind.in_(("game_payout", "game_forfeit", "game_refund")),
        )
        result = await self.session.execute(stmt)
        return int(result.scalar_one()) > 0
