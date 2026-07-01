"""Per-guild welcome / goodbye message settings (one row per guild)."""

from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base, TimestampMixin


class WelcomeConfig(Base, TimestampMixin):
    __tablename__ = "welcome_config"

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    # Templates support {user}, {name}, {server}, {count}.
    welcome_channel_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    welcome_message: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    welcome_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    goodbye_channel_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    goodbye_message: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    goodbye_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
