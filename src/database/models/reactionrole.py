"""A role granted by reacting to a message with an emoji."""

from __future__ import annotations

from sqlalchemy import BigInteger, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base, IdMixin, TimestampMixin


class ReactionRole(Base, IdMixin, TimestampMixin):
    __tablename__ = "reaction_roles"
    __table_args__ = (
        UniqueConstraint("message_id", "emoji", name="uq_reactionrole_msg_emoji"),
        Index("ix_reactionrole_message", "message_id"),
    )

    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    emoji: Mapped[str] = mapped_column(String(64), nullable=False)  # unicode char or <:name:id>
    role_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
