"""Per-guild per-user message tally, for cross-server moderation lookups.

One row per (guild_id, user_id): how many messages that user has sent in that
guild. Written by the msgcounter cog's batched flush; read by ``,messages`` to
show where a user is active across every server the bot shares with them.
"""

from __future__ import annotations

from sqlalchemy import BigInteger, Index
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base, TimestampMixin


class UserMessageCount(Base, TimestampMixin):
    """Total messages one user has sent in one guild."""

    __tablename__ = "user_message_counts"
    __table_args__ = (
        # The lookup is "all guilds for this user", so index user_id (the composite
        # PK is guild_id-leading and can't serve it).
        Index("ix_msgcount_user", "user_id"),
    )

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
