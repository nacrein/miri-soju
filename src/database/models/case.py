"""Unified moderation record: warnings, notes, and logged actions as one history."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import BigInteger, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base, IdMixin, TimestampMixin


class ModCase(Base, IdMixin, TimestampMixin):
    """One moderation event against a user in a guild. The case id is the reference."""

    __tablename__ = "mod_cases"
    __table_args__ = (
        Index("ix_mod_cases_guild_user", "guild_id", "user_id"),
    )

    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    moderator_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # warn, note, ban, kick, timeout...
    reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
