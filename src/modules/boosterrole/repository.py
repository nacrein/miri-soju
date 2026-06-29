"""Data access for booster roles: the config row and the per-member role records.

Standard async SQLAlchemy, mirroring ``src/modules/leveling/repository.py``."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models.boosterrole import BoosterRole, BoosterRoleConfig


class BoosterRoleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ── config ────────────────────────────────────────────────────────────────

    async def get_config(self, guild_id: int) -> BoosterRoleConfig | None:
        return await self.session.get(BoosterRoleConfig, guild_id)

    async def get_or_create_config(self, guild_id: int) -> BoosterRoleConfig:
        cfg = await self.session.get(BoosterRoleConfig, guild_id)
        if cfg is None:
            cfg = BoosterRoleConfig(guild_id=guild_id)
            self.session.add(cfg)
            await self.session.flush()
        return cfg

    # ── role records ────────────────────────────────────────────────────────────

    async def get_role(self, guild_id: int, user_id: int) -> BoosterRole | None:
        stmt = select(BoosterRole).where(
            BoosterRole.guild_id == guild_id, BoosterRole.user_id == user_id
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def upsert_role(
        self, guild_id: int, user_id: int, role_id: int, name: str, color: int, icon: str | None
    ) -> None:
        existing = await self.get_role(guild_id, user_id)
        if existing is not None:
            existing.role_id = role_id
            existing.name, existing.color, existing.icon = name, color, icon
        else:
            self.session.add(BoosterRole(
                guild_id=guild_id, user_id=user_id, role_id=role_id,
                name=name, color=color, icon=icon,
            ))

    async def update_role_fields(self, guild_id: int, user_id: int, fields: dict) -> bool:
        role = await self.get_role(guild_id, user_id)
        if role is None:
            return False
        for key, value in fields.items():
            setattr(role, key, value)
        return True

    async def delete_role(self, guild_id: int, user_id: int) -> bool:
        stmt = delete(BoosterRole).where(
            BoosterRole.guild_id == guild_id, BoosterRole.user_id == user_id
        )
        return ((await self.session.execute(stmt)).rowcount or 0) > 0

    async def clear_by_role(self, guild_id: int, role_id: int) -> bool:
        stmt = delete(BoosterRole).where(
            BoosterRole.guild_id == guild_id, BoosterRole.role_id == role_id
        )
        return ((await self.session.execute(stmt)).rowcount or 0) > 0

    async def list_roles(self, guild_id: int) -> list[BoosterRole]:
        stmt = select(BoosterRole).where(BoosterRole.guild_id == guild_id)
        return list((await self.session.execute(stmt)).scalars().all())

    async def list_all(self) -> list[BoosterRole]:
        return list((await self.session.execute(select(BoosterRole))).scalars().all())
