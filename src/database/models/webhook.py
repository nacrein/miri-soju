"""Managed webhooks, referenced by a short per-guild id."""

from __future__ import annotations

from sqlalchemy import BigInteger, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base, IdMixin, TimestampMixin


class ManagedWebhook(Base, IdMixin, TimestampMixin):
    __tablename__ = "managed_webhooks"
    __table_args__ = (UniqueConstraint("guild_id", "short_id", name="uq_webhook_guild_short"),)

    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    webhook_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    short_id: Mapped[str] = mapped_column(String(12), nullable=False)
