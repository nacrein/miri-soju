"""Data access for leveling."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models.level import ChannelMultiplier, LevelConfig, LevelReward, MemberLevel


class LevelingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ── config ────────────────────────────────────────────────────────────────

    async def get_config(self, guild_id: int) -> Optional[LevelConfig]:
        return await self.session.get(LevelConfig, guild_id)

    async def get_or_create_config(self, guild_id: int) -> LevelConfig:
        cfg = await self.session.get(LevelConfig, guild_id)
        if cfg is None:
            cfg = LevelConfig(guild_id=guild_id)
            self.session.add(cfg)
            await self.session.flush()
        return cfg

    # ── member progress ─────────────────────────────────────────────────────

    async def get_member(self, guild_id: int, user_id: int) -> Optional[MemberLevel]:
        stmt = select(MemberLevel).where(MemberLevel.guild_id == guild_id, MemberLevel.user_id == user_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_or_create_member(self, guild_id: int, user_id: int) -> MemberLevel:
        member = await self.get_member(guild_id, user_id)
        if member is None:
            member = MemberLevel(guild_id=guild_id, user_id=user_id)
            self.session.add(member)
            await self.session.flush()
        return member

    async def rank_by_xp(self, guild_id: int, xp: int) -> int:
        stmt = select(func.count()).select_from(MemberLevel).where(
            MemberLevel.guild_id == guild_id, MemberLevel.xp > xp
        )
        return int((await self.session.execute(stmt)).scalar_one()) + 1

    async def reset_member(self, guild_id: int, user_id: int) -> bool:
        stmt = delete(MemberLevel).where(MemberLevel.guild_id == guild_id, MemberLevel.user_id == user_id)
        return ((await self.session.execute(stmt)).rowcount or 0) > 0

    async def reset_all(self, guild_id: int) -> int:
        stmt = delete(MemberLevel).where(MemberLevel.guild_id == guild_id)
        return (await self.session.execute(stmt)).rowcount or 0

    async def top_by_xp(self, guild_id: int, limit: int) -> list[tuple[int, int]]:
        stmt = (select(MemberLevel.user_id, MemberLevel.xp)
                .where(MemberLevel.guild_id == guild_id)
                .order_by(MemberLevel.xp.desc()).limit(limit))
        return [(r[0], r[1]) for r in (await self.session.execute(stmt)).all()]

    async def top_by_voice(self, guild_id: int, limit: int) -> list[tuple[int, int]]:
        stmt = (select(MemberLevel.user_id, MemberLevel.voice_minutes)
                .where(MemberLevel.guild_id == guild_id, MemberLevel.voice_minutes > 0)
                .order_by(MemberLevel.voice_minutes.desc()).limit(limit))
        return [(r[0], r[1]) for r in (await self.session.execute(stmt)).all()]

    # ── rewards ───────────────────────────────────────────────────────────────

    async def _reward(self, guild_id: int, level: int) -> Optional[LevelReward]:
        stmt = select(LevelReward).where(LevelReward.guild_id == guild_id, LevelReward.level == level)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def add_reward(self, guild_id: int, level: int, role_id: int) -> None:
        existing = await self._reward(guild_id, level)
        if existing is not None:
            existing.role_id = role_id
        else:
            self.session.add(LevelReward(guild_id=guild_id, level=level, role_id=role_id))

    async def remove_reward(self, guild_id: int, level: int) -> bool:
        stmt = delete(LevelReward).where(LevelReward.guild_id == guild_id, LevelReward.level == level)
        return ((await self.session.execute(stmt)).rowcount or 0) > 0

    async def list_rewards(self, guild_id: int) -> list[tuple[int, int]]:
        stmt = (select(LevelReward.level, LevelReward.role_id)
                .where(LevelReward.guild_id == guild_id).order_by(LevelReward.level.asc()))
        return [(r[0], r[1]) for r in (await self.session.execute(stmt)).all()]

    async def rewards_up_to(self, guild_id: int, level: int) -> list[tuple[int, int]]:
        stmt = select(LevelReward.level, LevelReward.role_id).where(
            LevelReward.guild_id == guild_id, LevelReward.level <= level
        )
        return [(r[0], r[1]) for r in (await self.session.execute(stmt)).all()]

    # ── channel multipliers ───────────────────────────────────────────────────

    async def _mult(self, guild_id: int, channel_id: int) -> Optional[ChannelMultiplier]:
        stmt = select(ChannelMultiplier).where(
            ChannelMultiplier.guild_id == guild_id, ChannelMultiplier.channel_id == channel_id
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def set_multiplier(self, guild_id: int, channel_id: int, multiplier: float) -> None:
        existing = await self._mult(guild_id, channel_id)
        if existing is not None:
            existing.multiplier = multiplier
        else:
            self.session.add(ChannelMultiplier(guild_id=guild_id, channel_id=channel_id, multiplier=multiplier))

    async def remove_multiplier(self, guild_id: int, channel_id: int) -> bool:
        stmt = delete(ChannelMultiplier).where(
            ChannelMultiplier.guild_id == guild_id, ChannelMultiplier.channel_id == channel_id
        )
        return ((await self.session.execute(stmt)).rowcount or 0) > 0

    async def list_multipliers(self, guild_id: int) -> list[tuple[int, float]]:
        stmt = select(ChannelMultiplier.channel_id, ChannelMultiplier.multiplier).where(
            ChannelMultiplier.guild_id == guild_id
        )
        return [(r[0], r[1]) for r in (await self.session.execute(stmt)).all()]
