"""FastAPI dependencies: the logged-in user, and the guild-admin gate.

The session cookie (signed by ``SessionMiddleware``) holds the authenticated user
and the set of guilds they may manage — computed once at login as
``user's admin guilds ∩ bot's guilds``. Every config endpoint depends on
``require_guild`` so a user can only ever touch a guild that set vouched for; the
guild id in the URL is never trusted on its own.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, Path, Request, status

SESSION_USER_KEY = "user"
SESSION_GUILDS_KEY = "guilds"  # {guild_id(str): {"name", "icon"}}


def get_current_user(request: Request) -> dict:
    user = request.session.get(SESSION_USER_KEY)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
    return user


def get_manageable_guilds(request: Request) -> dict[str, dict]:
    return request.session.get(SESSION_GUILDS_KEY, {})


async def require_guild(
    guild_id: int = Path(..., description="Discord guild (server) id"),
    request: Request = None,  # type: ignore[assignment]
    _user: dict = Depends(get_current_user),
) -> int:
    """Authorize the caller for ``guild_id`` and return it.

    401 if not logged in (via ``get_current_user``); 403 if logged in but the
    guild isn't one this session may manage (not an admin there, or the bot isn't
    in it).
    """
    manageable = get_manageable_guilds(request)
    if str(guild_id) not in manageable:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't manage that server, or the bot isn't in it.",
        )
    return guild_id
