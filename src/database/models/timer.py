"""A recurring channel message."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base, IdMixin, TimestampMixin


class Timer(Base, IdMixin, TimestampMixin):
    __tablename__ = "timers"
    __table_args__ = (Index("ix_timers_next_run", "next_run"),)

    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    message: Mapped[str] = mapped_column(String(2000), nullable=False)
    next_run: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
