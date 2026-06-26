"""Data access for per-guild config."""

from __future__ import annotations

from src.core.repository import BaseRepository
from src.database.models.guild import GuildConfig


class GuildConfigRepository(BaseRepository[GuildConfig]):
    model = GuildConfig

    async def get_or_create(self, guild_id: int) -> GuildConfig:
        config = await self.get(guild_id)
        if config is None:
            config = GuildConfig(guild_id=guild_id)
            self.add(config)
            await self.session.flush()
        return config
