"""Tag storage logic. No discord here — just the data."""

from __future__ import annotations

from src.database.models.tag import Tag
from src.database.session import get_session
from src.modules.tags.repository import TagRepository


async def get(guild_id: int, name: str) -> Tag | None:
    async with get_session() as session:
        return await TagRepository(session).get(guild_id, name)


async def create(guild_id: int, name: str, content: str, author_id: int) -> bool:
    async with get_session() as session:
        return await TagRepository(session).create(guild_id, name, content, author_id)


async def set_content(guild_id: int, name: str, content: str) -> bool:
    async with get_session() as session:
        return await TagRepository(session).set_content(guild_id, name, content)


async def delete(guild_id: int, name: str) -> bool:
    async with get_session() as session:
        return await TagRepository(session).delete(guild_id, name)


async def use(guild_id: int, name: str) -> str | None:
    """Fetch a tag's content and count the use, in one session. None if it's missing."""
    async with get_session() as session:
        repo = TagRepository(session)
        tag = await repo.get(guild_id, name)
        if tag is None:
            return None
        await repo.bump_uses(guild_id, name)
        return tag.content


async def list_names(guild_id: int) -> list[str]:
    async with get_session() as session:
        return await TagRepository(session).list_names(guild_id)
