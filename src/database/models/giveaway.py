"""A timed giveaway and its entrants."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base, IdMixin, TimestampMixin


class Giveaway(Base, IdMixin, TimestampMixin):
    __tablename__ = "giveaways"
    __table_args__ = (Index("ix_giveaways_ends_at", "ends_at"),)

    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    prize: Mapped[str] = mapped_column(String(256), nullable=False)
    winners: Mapped[int] = mapped_column(Integer, nullable=False)
    host_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class GiveawayEntry(Base, IdMixin, TimestampMixin):
    __tablename__ = "giveaway_entries"
    __table_args__ = (
        UniqueConstraint("giveaway_id", "user_id", name="uq_giveaway_entry"),
    )

    giveaway_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
