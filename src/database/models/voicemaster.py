"""VoiceMaster state: per-guild config + the live temporary voice channels.

NOTE: adds two new tables (``voicemaster_config``, ``voicemaster_channels``) — it
needs an Alembic migration wherever the schema is managed by migrations. (The test
suite builds the schema with ``Base.metadata.create_all``, so tests need nothing.)
"""

from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base, IdMixin, TimestampMixin


class VoiceMasterConfig(Base, TimestampMixin):
    """Per-guild VoiceMaster settings (one row per guild)."""

    __tablename__ = "voicemaster_config"

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    create_channel_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    panel_channel_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    panel_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class VoiceMasterChannel(Base, IdMixin, TimestampMixin):
    """One live temporary voice channel and its current owner."""

    __tablename__ = "voicemaster_channels"
    __table_args__ = (
        UniqueConstraint("guild_id", "channel_id", name="uq_vmchannel_guild_channel"),
    )

    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    owner_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
