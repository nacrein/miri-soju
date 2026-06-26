"""Append-only economy transaction ledger. Staff-only; never mutated."""

from __future__ import annotations

from typing import Optional

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
    )

    discord_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)  # daily, work, gamble_win...
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    balance_after: Mapped[int] = mapped_column(BigInteger, nullable=False)
    counterparty_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    note: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
