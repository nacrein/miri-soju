"""Persisted unhandled errors, looked up by their short code via ``,staff error``.

When the global handler mints a code like ``7187AE`` for an unexpected exception, a
row is written here so staff can later diagnose it without grepping logs.

NOTE: adds the ``error_logs`` table; needs an Alembic migration.
"""

from __future__ import annotations

from sqlalchemy import BigInteger, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base, IdMixin, TimestampMixin


class ErrorLog(Base, IdMixin, TimestampMixin):
    __tablename__ = "error_logs"
    __table_args__ = (Index("ix_error_logs_code", "code"),)

    code: Mapped[str] = mapped_column(String(6), nullable=False)  # 6-char hex shown to the user
    context: Mapped[str] = mapped_column(String(200), nullable=False)  # e.g. "command 'vm enable'"
    exc_type: Mapped[str] = mapped_column(String(120), nullable=False)
    message: Mapped[str] = mapped_column(String(1000), nullable=False)
    traceback: Mapped[str | None] = mapped_column(Text, nullable=True)
    guild_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
