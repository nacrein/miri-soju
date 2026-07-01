"""Append-only log of command invocations, for staff analytics.

One row per successfully completed command (written by the analytics cog's
``on_command_completion`` listener). Never mutated. Kept deliberately small — the
command's qualified name, who ran it, and where — so it stays cheap to write on
the hot path and cheap to aggregate for the dashboard's staff view.

NOTE: adds the ``command_usage`` table; needs an Alembic migration.
"""

from __future__ import annotations

from sqlalchemy import BigInteger, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base, IdMixin, TimestampMixin


class CommandUsage(Base, IdMixin, TimestampMixin):
    __tablename__ = "command_usage"
    __table_args__ = (
        # "most-used commands" groups by name; the time index powers "usage over time".
        Index("ix_command_usage_command", "command"),
        Index("ix_command_usage_created", "created_at"),
    )

    # qualified command name, e.g. "automod enable"
    command: Mapped[str] = mapped_column(String(100), nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    guild_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)  # None in DMs
