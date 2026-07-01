"""Blacklist: users barred from the bot entirely.

A single gate keyed by ``scope``:
  * 'bot' - blocked from every command (enforced by a global check).

The ``scope`` column is kept (composite (discord_id, scope) primary key) so the
gate can grow more scopes later, but only 'bot' is currently valid. Managed with
,staff blacklist / unblacklist.

NOTE: adds the ``blacklists`` table; needs an Alembic migration.
"""

from __future__ import annotations

from sqlalchemy import BigInteger, CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base, TimestampMixin


class Blacklist(Base, TimestampMixin):
    __tablename__ = "blacklists"
    __table_args__ = (
        CheckConstraint("scope = 'bot'", name="chk_blacklist_scope"),
    )

    discord_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    scope: Mapped[str] = mapped_column(String(16), primary_key=True)  # 'bot'
    reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    added_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
