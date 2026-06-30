"""Starboard: per-guild config and the mirror of which messages reached the board."""

from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base, IdMixin, TimestampMixin


class StarboardConfig(Base, TimestampMixin):
    __tablename__ = "starboard_config"

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    channel_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    star_emoji: Mapped[str] = mapped_column(String(64), nullable=False, default="⭐")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    self_star: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class StarboardEntry(Base, IdMixin, TimestampMixin):
    """One source message that reached the board, linked to its board post."""

    __tablename__ = "starboard_entries"
    __table_args__ = (
        UniqueConstraint("guild_id", "message_id", name="uq_starboard_guild_msg"),
    )

    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    board_message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    star_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
