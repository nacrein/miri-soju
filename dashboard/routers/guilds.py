"""Guild discovery and per-guild metadata (roles + channels for the dropdowns)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from dashboard import discord_api
from dashboard.deps import get_current_user, get_manageable_guilds, require_guild
from dashboard.schemas import ChannelOut, GuildMetaOut, GuildOut, RoleOut

router = APIRouter(tags=["guilds"])


@router.get("/guilds", response_model=list[GuildOut])
async def list_guilds(
    request: Request, _user: dict = Depends(get_current_user)
) -> list[GuildOut]:
    """Servers the logged-in user may configure (admin there + bot present).

    Requires auth (``get_current_user`` → 401 when logged out) so an anonymous
    request gets 401, not an empty 200.
    """
    guilds = get_manageable_guilds(request)
    return [
        GuildOut(id=gid, name=g["name"], icon=g.get("icon"))
        for gid, g in guilds.items()
    ]


@router.get("/guilds/{guild_id}/meta", response_model=GuildMetaOut)
async def guild_meta(
    request: Request, guild_id: int = Depends(require_guild)
) -> GuildMetaOut:
    """Roles and text channels for a guild — used to populate config selects."""
    info = get_manageable_guilds(request)[str(guild_id)]
    roles = await discord_api.fetch_guild_roles(guild_id)
    channels = await discord_api.fetch_guild_channels(guild_id)
    voice = await discord_api.fetch_guild_voice_channels(guild_id)
    return GuildMetaOut(
        guild=GuildOut(id=str(guild_id), name=info["name"], icon=info.get("icon")),
        roles=[RoleOut(**r) for r in roles],
        channels=[ChannelOut(id=c["id"], name=c["name"]) for c in channels],
        voice_channels=[ChannelOut(id=c["id"], name=c["name"]) for c in voice],
    )
