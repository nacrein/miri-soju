"""Runtime-managed staff roster: the admin/staff permission tiers.

The bot owner is discord.py's built-in owner and is never stored here. This table
holds the two DB-backed tiers granted at runtime with ,staff promote / demote, so
staff membership survives restarts instead of living only in the STAFF_IDS env var.

NOTE: adds the ``staff_members`` table; needs an Alembic migration.
"""

from __future__ import annotations

from sqlalchemy import BigInteger, CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base, TimestampMixin


class StaffMember(Base, TimestampMixin):
    """One row per user granted a tier. Keyed on Discord user ID, like Player."""

    __tablename__ = "staff_members"
    __table_args__ = (
        # A named check (not a native ENUM) so it round-trips through the SQLite
        # test harness the migration-drift test uses.
        CheckConstraint("tier in ('staff', 'admin')", name="chk_staff_member_tier"),
    )

    discord_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tier: Mapped[str] = mapped_column(String(16), nullable=False)  # 'staff' | 'admin'
    # Who granted this tier (owner/admin id), for an audit trail. Nullable so a
    # future backfill or a manual insert doesn't need to invent an actor.
    added_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
