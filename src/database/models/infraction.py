"""Moderation warnings, recorded per-guild. A server's records are its own."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import BigInteger, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base, IdMixin, TimestampMixin


class Infraction(Base, IdMixin, TimestampMixin):
    """A warning issued to a user in a specific guild. Mods act on these manually."""

    __tablename__ = "infractions"
    __table_args__ = (
        # "this user's warnings in this server", newest first.
        Index("ix_infractions_guild_user", "guild_id", "user_id"),
    )

    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    moderator_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
