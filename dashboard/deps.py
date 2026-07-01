"""FastAPI dependencies: the logged-in user, and the guild-admin gate.

The session cookie (signed by ``SessionMiddleware``) holds the authenticated user
and the set of guilds they may manage — computed once at login as
``user's admin guilds ∩ bot's guilds``. Every config endpoint depends on
``require_guild`` so a user can only ever touch a guild that set vouched for; the
guild id in the URL is never trusted on its own.
"""

from __future__ import annotations

from functools import lru_cache

from fastapi import Depends, HTTPException, Path, Request, status

from config.settings import get_settings

SESSION_USER_KEY = "user"
SESSION_GUILDS_KEY = "guilds"  # {guild_id(str): {"name", "icon"}}


@lru_cache
def staff_user_ids() -> frozenset[int]:
    """The Discord user ids allowed into the staff area.

    Reuses the *bot's* own trust config (``OWNER_ID`` + ``STAFF_IDS``) so the web
    staff area and the in-Discord ``,staff`` commands admit exactly the same people
    and can't drift. Cached: the env is fixed for the process's life."""
    settings = get_settings()
    ids: set[int] = set()
    if settings.owner_id is not None:
        ids.add(int(settings.owner_id))
    for part in settings.staff_ids.split(","):
        part = part.strip()
        if part.isdigit():
            ids.add(int(part))
    return frozenset(ids)


def is_staff_user(user_id: int | str) -> bool:
    return int(user_id) in staff_user_ids()


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


def require_staff(user: dict = Depends(get_current_user)) -> dict:
    """Authorize a bot-staff-only endpoint and return the staff user.

    401 if not logged in (via ``get_current_user``); 403 if logged in but not one
    of the bot's owner/staff ids. Recomputed from the user's id against the live
    config on every call — the session's ``is_staff`` flag is only a UI hint."""
    if not is_staff_user(user["id"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Staff only.",
        )
    return user
