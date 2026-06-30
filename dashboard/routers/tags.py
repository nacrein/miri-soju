"""Tags endpoints — per-guild custom commands (a CRUD list).

Names are normalized to lowercase to match how the bot resolves ``,tag <name>``.
The dashboard user is recorded as the author of tags created here."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from dashboard.deps import get_current_user, require_guild
from dashboard.schemas import TagContentIn, TagIn, TagOut, TagsOut
from src.database.session import get_session
from src.modules.tags.repository import TagRepository

router = APIRouter(prefix="/guilds/{guild_id}/tags", tags=["tags"])


async def _load(session, guild_id: int) -> TagsOut:
    rows = await TagRepository(session).list_for_guild(guild_id)
    return TagsOut(tags=[
        TagOut(name=t.name, content=t.content, author_id=str(t.author_id), uses=t.uses)
        for t in rows
    ])


@router.get("", response_model=TagsOut)
async def list_tags(guild_id: int = Depends(require_guild)) -> TagsOut:
    async with get_session() as session:
        return await _load(session, guild_id)


@router.post("", response_model=TagsOut, status_code=status.HTTP_201_CREATED)
async def create_tag(
    body: TagIn,
    guild_id: int = Depends(require_guild),
    user: dict = Depends(get_current_user),
) -> TagsOut:
    name = body.name.strip().lower()
    async with get_session() as session:
        created = await TagRepository(session).create(
            guild_id, name, body.content, int(user["id"])
        )
        if not created:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A tag named '{name}' already exists.",
            )
        return await _load(session, guild_id)


@router.put("/{name}", response_model=TagsOut)
async def edit_tag(
    name: str, body: TagContentIn, guild_id: int = Depends(require_guild)
) -> TagsOut:
    async with get_session() as session:
        repo = TagRepository(session)
        if not await repo.set_content(guild_id, name.strip().lower(), body.content):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="No tag with that name."
            )
        return await _load(session, guild_id)


@router.delete("/{name}", response_model=TagsOut)
async def delete_tag(name: str, guild_id: int = Depends(require_guild)) -> TagsOut:
    async with get_session() as session:
        await TagRepository(session).delete(guild_id, name.strip().lower())
        return await _load(session, guild_id)
