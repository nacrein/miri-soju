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
from src.core import staff_roster

SESSION_USER_KEY = "user"
SESSION_GUILDS_KEY = "guilds"  # {guild_id(str): {"name", "icon"}}


@lru_cache
def staff_user_ids() -> frozenset[int]:
    """The env *bootstrap floor* for staff access: ``OWNER_ID`` + ``STAFF_IDS``.

    Runtime staff live in the DB ``staff_members`` roster (managed with
    ``,staff promote`` / ``demote``); this env set is unioned on top so the owner and
    any pinned ids always have web access — even against an empty table or a brand-new
    deploy — mirroring how the bot exempts the owner and treats ``STAFF_IDS`` as a
    legacy floor. Cached: the env is fixed for the process's life."""
    settings = get_settings()
    ids: set[int] = set()
    if settings.owner_id is not None:
        ids.add(int(settings.owner_id))
    for part in settings.staff_ids.split(","):
        part = part.strip()
        if part.isdigit():
            ids.add(int(part))
    return frozenset(ids)


async def is_staff_user(user_id: int | str) -> bool:
    """Whether a user may enter the staff area: the env floor OR the DB roster.

    Checks the cheap env floor first — no DB round-trip and still lets the owner in if
    the database is briefly down — then falls back to the runtime ``staff_members``
    roster via the *same* repository the bot uses for ``,staff`` (``staff_roster``), so
    there is one source of truth and a Discord ``,staff promote`` grants web access with
    no restart. The roster read is uncached (see ``staff_roster.is_staff_member``), so a
    ``,staff demote`` revokes access on the very next request."""
    uid = int(user_id)
    if uid in staff_user_ids():
        return True
    return await staff_roster.is_staff_member(uid)


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


async def require_staff(user: dict = Depends(get_current_user)) -> dict:
    """Authorize a bot-staff-only endpoint and return the staff user.

    401 if not logged in (via ``get_current_user``); 403 unless the user is on the
    bot's DB staff roster or the env floor (``is_staff_user``). Recomputed against the
    live roster on every request — a promote/demote in Discord takes effect here with
    no restart, and the session's ``is_staff`` flag is only a UI hint."""
    if not await is_staff_user(user["id"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Staff only.",
        )
    return user
