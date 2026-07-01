"""A role automatically granted to every member when they join."""

from __future__ import annotations

from sqlalchemy import BigInteger, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base, IdMixin, TimestampMixin


class AutoRole(Base, IdMixin, TimestampMixin):
    __tablename__ = "auto_roles"
    __table_args__ = (
        UniqueConstraint("guild_id", "role_id", name="uq_autorole_guild_role"),
        Index("ix_autorole_guild", "guild_id"),
    )

    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    role_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
