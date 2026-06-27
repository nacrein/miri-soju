"""A message that reposts itself to the bottom of a channel."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base, TimestampMixin


class StickyMessage(Base, TimestampMixin):
    __tablename__ = "sticky_messages"

    channel_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    content: Mapped[str] = mapped_column(String(2000), nullable=False)
    last_message_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
