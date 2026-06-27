"""Per-guild configuration."""

from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base, TimestampMixin


class GuildConfig(Base, TimestampMixin):
    """Per-server settings, keyed on guild ID. Created on first configuration."""

    __tablename__ = "guild_config"

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    # Custom command prefix. None = use the global default (",").
    prefix: Mapped[str | None] = mapped_column(String(8), nullable=True)

    # Audit log channel. None = logging off for this server.
    log_channel_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # Per-event toggles.
    log_joins: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    log_leaves: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    log_message_delete: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    log_message_edit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    log_mod_actions: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
