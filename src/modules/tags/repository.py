"""Data access for tags."""

from __future__ import annotations

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models.tag import Tag


class TagRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, guild_id: int, name: str) -> Tag | None:
        stmt = select(Tag).where(Tag.guild_id == guild_id, Tag.name == name)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def create(self, guild_id: int, name: str, content: str, author_id: int) -> bool:
        if await self.get(guild_id, name) is not None:
            return False
        self.session.add(
            Tag(guild_id=guild_id, name=name, content=content, author_id=author_id)
        )
        return True

    async def set_content(self, guild_id: int, name: str, content: str) -> bool:
        stmt = (
            update(Tag)
            .where(Tag.guild_id == guild_id, Tag.name == name)
            .values(content=content)
        )
        return ((await self.session.execute(stmt)).rowcount or 0) > 0

    async def delete(self, guild_id: int, name: str) -> bool:
        stmt = delete(Tag).where(Tag.guild_id == guild_id, Tag.name == name)
        return ((await self.session.execute(stmt)).rowcount or 0) > 0

    async def bump_uses(self, guild_id: int, name: str) -> None:
        stmt = (
            update(Tag)
            .where(Tag.guild_id == guild_id, Tag.name == name)
            .values(uses=Tag.uses + 1)
        )
        await self.session.execute(stmt)

    async def list_names(self, guild_id: int) -> list[str]:
        stmt = (
            select(Tag.name).where(Tag.guild_id == guild_id).order_by(Tag.name.asc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def list_for_guild(self, guild_id: int) -> list[Tag]:
        """Full tag rows for a guild (used by the dashboard's tag manager)."""
        stmt = select(Tag).where(Tag.guild_id == guild_id).order_by(Tag.name.asc())
        return list((await self.session.execute(stmt)).scalars().all())
