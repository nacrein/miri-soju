"""Data access for starboard config and entries."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models.starboard import StarboardConfig, StarboardEntry


class StarboardRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ── config ───────────────────────────────────────────────────────────────
    async def get_config(self, guild_id: int) -> StarboardConfig | None:
        return await self.session.get(StarboardConfig, guild_id)

    async def get_or_create_config(self, guild_id: int) -> StarboardConfig:
        config = await self.session.get(StarboardConfig, guild_id)
        if config is None:
            config = StarboardConfig(guild_id=guild_id)
            self.session.add(config)
            await self.session.flush()  # materialize column defaults (threshold=3, ...)
        return config

    # ── entries ──────────────────────────────────────────────────────────────
    async def get_entry(self, guild_id: int, message_id: int) -> StarboardEntry | None:
        stmt = select(StarboardEntry).where(
            StarboardEntry.guild_id == guild_id, StarboardEntry.message_id == message_id
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def upsert_entry(
        self, guild_id: int, message_id: int, board_message_id: int, star_count: int
    ) -> None:
        entry = await self.get_entry(guild_id, message_id)
        if entry is None:
            self.session.add(StarboardEntry(
                guild_id=guild_id, message_id=message_id,
                board_message_id=board_message_id, star_count=star_count,
            ))
        else:
            entry.board_message_id = board_message_id
            entry.star_count = star_count

    async def delete_entry(self, guild_id: int, message_id: int) -> None:
        await self.session.execute(delete(StarboardEntry).where(
            StarboardEntry.guild_id == guild_id, StarboardEntry.message_id == message_id
        ))
