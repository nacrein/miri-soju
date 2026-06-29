"""Vanity state: per-guild config + the durable mirror of who is currently repping.

NOTE: adds two new tables (``vanity_config``, ``vanity_trackers``) — it needs an
Alembic migration wherever the schema is managed by migrations. (The test suite
builds the schema with ``Base.metadata.create_all``, so tests need nothing.)
"""

from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base, IdMixin, TimestampMixin


class VanityConfig(Base, TimestampMixin):
    """Per-guild vanity-rep settings (one row per guild)."""

    __tablename__ = "vanity_config"

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    role_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    channel_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    # Thank-you template; supports {user} and {vanity}.
    message_template: Mapped[str | None] = mapped_column(String(500), nullable=True)


class VanityTracker(Base, IdMixin, TimestampMixin):
    """One member currently repping the vanity. ``created_at`` is when they started."""

    __tablename__ = "vanity_trackers"
    __table_args__ = (
        UniqueConstraint("guild_id", "user_id", name="uq_vanitytracker_guild_user"),
    )

    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
