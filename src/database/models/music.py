"""Music config: per-guild DJ role, command channel, default volume.

Queue, history, and now-playing state are deliberately NOT persisted here — they live
in the wavelink Player (backed by the Lavalink node) and reset on restart. Only this
small per-guild config row is stored.
"""

from __future__ import annotations

from sqlalchemy import BigInteger, Integer
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base, TimestampMixin


class MusicConfig(Base, TimestampMixin):
    """Per-guild music settings (one row per guild)."""

    __tablename__ = "music_config"

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    dj_role_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    command_channel_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    default_volume: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
