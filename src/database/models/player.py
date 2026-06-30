"""The shared player account."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Index, Integer, text
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base, TimestampMixin


class Player(Base, TimestampMixin):
    """A player, keyed on Discord user ID. Holds identity, currency, economy state."""

    __tablename__ = "players"
    __table_args__ = (
        # Currency can never go negative; the final backstop against bad math.
        CheckConstraint("wallet >= 0", name="chk_player_wallet_nonneg"),
        CheckConstraint("vault >= 0", name="chk_player_vault_nonneg"),
        CheckConstraint("vault <= vault_capacity", name="chk_player_vault_within_cap"),
        CheckConstraint("vault_capacity >= 0", name="chk_player_vault_cap_nonneg"),
        # Net worth is the leaderboard/rank sort key; a functional index on the
        # expression lets Postgres order by it without scanning + summing rows.
        Index("ix_players_net_worth", text("(wallet + vault) DESC")),
    )

    discord_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    # Spendable + stealable.
    wallet: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    # Safe, inert until withdrawn. Bounded by vault_capacity.
    vault: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    vault_capacity: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)

    # Passive generator.
    generator_tier: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    generator_claimed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Faucet cooldown anchors (evaluated on read; no background ticker).
    last_daily_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_work_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_pray_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_steal_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Daily streak (0-7+; resets if a day is missed).
    daily_streak: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # When the user accepted the economy rules. None = not yet agreed; the economy
    # cog gates every command until this is set (see modules/economy/agreement.py).
    tos_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
