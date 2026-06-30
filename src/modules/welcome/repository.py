"""Data access for welcome/goodbye config."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models.welcome import WelcomeConfig


class WelcomeConfigRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, guild_id: int) -> WelcomeConfig | None:
        return await self.session.get(WelcomeConfig, guild_id)

    async def get_or_create(self, guild_id: int) -> WelcomeConfig:
        config = await self.session.get(WelcomeConfig, guild_id)
        if config is None:
            config = WelcomeConfig(guild_id=guild_id)
            self.session.add(config)
            await self.session.flush()  # materialize column defaults (enabled=False, ...)
        return config
