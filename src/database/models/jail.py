"""Jail state: the per-guild jail role and each jailed member's prior roles."""

from __future__ import annotations

from sqlalchemy import JSON, BigInteger, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base, IdMixin, TimestampMixin


class ModerationConfig(Base, TimestampMixin):
    """Per-guild moderation settings, keyed on guild ID."""

    __tablename__ = "moderation_config"

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    jail_role_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class JailedMember(Base, IdMixin, TimestampMixin):
    """A currently-jailed member and the role IDs to restore on release."""

    __tablename__ = "jailed_members"
    __table_args__ = (UniqueConstraint("guild_id", "user_id", name="uq_jailed_guild_user"),)

    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    prior_roles: Mapped[list[int]] = mapped_column(JSON, nullable=False, default=list)
