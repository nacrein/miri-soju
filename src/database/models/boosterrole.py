"""Booster-role state: per-guild config + each booster's persisted custom role.

The ``BoosterRole`` row stores name/color/icon as well as the role_id, so a reboost
can reconstruct the role *identically* even if the Discord role was deleted while
the member was unboosted.

NOTE: this adds two new tables (``booster_role_config``, ``booster_roles``) — it
needs an Alembic migration wherever the schema is managed by migrations. (The test
suite builds the schema with ``Base.metadata.create_all``, so tests need nothing.)
"""

from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base, IdMixin, TimestampMixin


class BoosterRoleConfig(Base, TimestampMixin):
    """Per-guild booster-role settings (one row per guild)."""

    __tablename__ = "booster_role_config"

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Whether the custom roles sit above (True) or below (False) the anchor role.
    hoist_above: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # The role the booster-role cohort is positioned relative to (None = no anchor).
    anchor_role_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class BoosterRole(Base, IdMixin, TimestampMixin):
    """One booster's custom role. Self-sufficient for faithful re-creation."""

    __tablename__ = "booster_roles"
    __table_args__ = (UniqueConstraint("guild_id", "user_id", name="uq_boosterrole_guild_user"),)

    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    role_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    color: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    icon: Mapped[str | None] = mapped_column(String(100), nullable=True)
