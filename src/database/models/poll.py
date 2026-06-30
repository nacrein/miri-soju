"""A button-vote poll and its (one-per-user) votes."""

from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base, IdMixin, TimestampMixin


class Poll(Base, IdMixin, TimestampMixin):
    __tablename__ = "polls"

    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    author_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    question: Mapped[str] = mapped_column(String(256), nullable=False)
    # Option labels, newline-joined (kept relational-free; options never contain \n).
    options_text: Mapped[str] = mapped_column(String(1000), nullable=False)
    closed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class PollVote(Base, IdMixin, TimestampMixin):
    __tablename__ = "poll_votes"
    __table_args__ = (
        UniqueConstraint("poll_id", "user_id", name="uq_pollvote_poll_user"),
    )

    poll_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    option_index: Mapped[int] = mapped_column(Integer, nullable=False)
