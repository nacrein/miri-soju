"""Blacklist: users barred from the bot entirely, or from the economy only.

Two independent gates keyed by ``scope``:
  * 'bot'     - blocked from every command (enforced by a global check).
  * 'economy' - blocked from economy commands only (enforced in the Economy
                cog's cog_check).

A user can be on both; the composite (discord_id, scope) primary key allows one
row per scope. Managed with ,staff blacklist / econban.

NOTE: adds the ``blacklists`` table; needs an Alembic migration.
"""

from __future__ import annotations

from sqlalchemy import BigInteger, CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base, TimestampMixin


class Blacklist(Base, TimestampMixin):
    __tablename__ = "blacklists"
    __table_args__ = (
        CheckConstraint("scope in ('bot', 'economy')", name="chk_blacklist_scope"),
    )

    discord_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    scope: Mapped[str] = mapped_column(String(16), primary_key=True)  # 'bot' | 'economy'
    reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    added_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
