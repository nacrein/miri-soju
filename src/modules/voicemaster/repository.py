"""Data access for VoiceMaster: the config row and the tracked-channel records.

Standard async SQLAlchemy, mirroring ``src/modules/leveling/repository.py``."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models.voicemaster import VoiceMasterChannel, VoiceMasterConfig


class VoiceMasterRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ── config ────────────────────────────────────────────────────────────────

    async def get_config(self, guild_id: int) -> VoiceMasterConfig | None:
        return await self.session.get(VoiceMasterConfig, guild_id)

    async def get_or_create_config(self, guild_id: int) -> VoiceMasterConfig:
        cfg = await self.session.get(VoiceMasterConfig, guild_id)
        if cfg is None:
            cfg = VoiceMasterConfig(guild_id=guild_id)
            self.session.add(cfg)
            await self.session.flush()
        return cfg

    # ── tracked channels ──────────────────────────────────────────────────────

    async def get_by_owner(self, guild_id: int, owner_id: int) -> VoiceMasterChannel | None:
        stmt = select(VoiceMasterChannel).where(
            VoiceMasterChannel.guild_id == guild_id, VoiceMasterChannel.owner_id == owner_id
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_channel(self, guild_id: int, channel_id: int) -> VoiceMasterChannel | None:
        stmt = select(VoiceMasterChannel).where(
            VoiceMasterChannel.guild_id == guild_id, VoiceMasterChannel.channel_id == channel_id
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def add_channel(self, guild_id: int, owner_id: int, channel_id: int) -> None:
        self.session.add(
            VoiceMasterChannel(guild_id=guild_id, owner_id=owner_id, channel_id=channel_id)
        )

    async def delete_channel(self, guild_id: int, channel_id: int) -> bool:
        stmt = delete(VoiceMasterChannel).where(
            VoiceMasterChannel.guild_id == guild_id, VoiceMasterChannel.channel_id == channel_id
        )
        return ((await self.session.execute(stmt)).rowcount or 0) > 0

    async def set_owner(self, guild_id: int, channel_id: int, new_owner_id: int) -> bool:
        record = await self.get_by_channel(guild_id, channel_id)
        if record is None:
            return False
        record.owner_id = new_owner_id
        return True

    async def list_tracked(self, guild_id: int) -> list[VoiceMasterChannel]:
        stmt = select(VoiceMasterChannel).where(VoiceMasterChannel.guild_id == guild_id)
        return list((await self.session.execute(stmt)).scalars().all())
