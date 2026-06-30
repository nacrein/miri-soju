"""A role granted by a button on a bot message."""

from __future__ import annotations

from sqlalchemy import BigInteger, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base, IdMixin, TimestampMixin


class ButtonRole(Base, IdMixin, TimestampMixin):
    __tablename__ = "button_roles"
    __table_args__ = (Index("ix_buttonrole_message", "message_id"),)

    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    role_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    label: Mapped[str | None] = mapped_column(String(80), nullable=True)
    emoji: Mapped[str | None] = mapped_column(String(64), nullable=True)
    style: Mapped[str] = mapped_column(String(16), nullable=False, default="secondary")
