"""Members and roles that moderation actions refuse to act on."""

from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base, IdMixin, TimestampMixin


class ImmuneEntry(Base, IdMixin, TimestampMixin):
    """A user or role protected from moderation in a guild."""

    __tablename__ = "immune_entries"
    __table_args__ = (UniqueConstraint("guild_id", "target_id", name="uq_immune_guild_target"),)

    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    target_id: Mapped[int] = mapped_column(BigInteger, nullable=False)  # a user or a role id
    is_role: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
