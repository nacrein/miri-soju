"""Append-only economy transaction ledger. Staff-only; never mutated."""

from __future__ import annotations

from sqlalchemy import BigInteger, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base, IdMixin, TimestampMixin


class Transaction(Base, IdMixin, TimestampMixin):
    """One bit movement. Written inside the same transaction as the balance change.

    amount is signed: positive = gain, negative = loss. balance_after is the
    wallet balance immediately after this movement, so impossible jumps are
    visible. Never updated or deleted.
    """

    __tablename__ = "transactions"
    __table_args__ = (
        # History lookups are "this user, newest first".
        Index("ix_transactions_user_time", "discord_id", "created_at"),
        Index("ix_transactions_type", "kind"),
        # Reconciliation pairs a game's stake to its resolution by this id.
        Index("ix_transactions_game_session", "game_session_id"),
    )

    discord_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)  # daily, work, gamble_win...
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    balance_after: Mapped[int] = mapped_column(BigInteger, nullable=False)
    counterparty_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    note: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # Set only on interactive-game rows (stake + its resolution share one id);
    # NULL for every other transaction kind.
    game_session_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
