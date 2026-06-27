"""Roles that remove themselves after a duration."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base, IdMixin, TimestampMixin


class TempRole(Base, IdMixin, TimestampMixin):
    """A temporary role assignment, lifted when expires_at passes."""

    __tablename__ = "temp_roles"
    __table_args__ = (Index("ix_temp_roles_expires", "expires_at"),)

    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    role_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
