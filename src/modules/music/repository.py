"""Data access for music config, mirroring src/modules/leveling/repository.py."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models.music import MusicConfig


class MusicRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_config(self, guild_id: int) -> MusicConfig | None:
        return await self.session.get(MusicConfig, guild_id)

    async def get_or_create_config(self, guild_id: int) -> MusicConfig:
        cfg = await self.session.get(MusicConfig, guild_id)
        if cfg is None:
            cfg = MusicConfig(guild_id=guild_id)
            self.session.add(cfg)
            await self.session.flush()
        return cfg
