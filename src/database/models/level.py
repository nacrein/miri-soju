"""Leveling state: per-guild settings, per-member progress, rewards, multipliers."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger, Boolean, DateTime, Float, Index, Integer, String, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base, IdMixin, TimestampMixin


class LevelConfig(Base, TimestampMixin):
    """Per-guild leveling settings."""

    __tablename__ = "level_config"

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    xp_per_message: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    message_cooldown: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    announce_mode: Mapped[str] = mapped_column(String(8), nullable=False, default="here")  # here/dm/channel
    announce_channel_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    level_up_message: Mapped[str] = mapped_column(
        String(500), nullable=False, default="{user} reached level **{level}**!"
    )


class MemberLevel(Base, IdMixin, TimestampMixin):
    """One member's progress in one guild."""

    __tablename__ = "member_levels"
    __table_args__ = (
        UniqueConstraint("guild_id", "user_id", name="uq_memberlevel_guild_user"),
        Index("ix_memberlevel_guild_xp", "guild_id", "xp"),
        Index("ix_memberlevel_guild_voice", "guild_id", "voice_minutes"),
    )

    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    xp: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    voice_minutes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    last_message_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class LevelReward(Base, IdMixin, TimestampMixin):
    """A role granted on reaching a level."""

    __tablename__ = "level_rewards"
    __table_args__ = (UniqueConstraint("guild_id", "level", name="uq_levelreward_guild_level"),)

    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    role_id: Mapped[int] = mapped_column(BigInteger, nullable=False)


class ChannelMultiplier(Base, IdMixin, TimestampMixin):
    """An XP multiplier for one channel. 0 disables XP there."""

    __tablename__ = "channel_multipliers"
    __table_args__ = (UniqueConstraint("guild_id", "channel_id", name="uq_chanmult_guild_channel"),)

    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    multiplier: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
