"""A per-guild custom text command (a "tag")."""

from __future__ import annotations

from sqlalchemy import BigInteger, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base, IdMixin, TimestampMixin


class Tag(Base, IdMixin, TimestampMixin):
    __tablename__ = "tags"
    __table_args__ = (
        UniqueConstraint("guild_id", "name", name="uq_tag_guild_name"),
        Index("ix_tag_guild_name", "guild_id", "name"),
    )

    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    content: Mapped[str] = mapped_column(String(2000), nullable=False)
    author_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    uses: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
