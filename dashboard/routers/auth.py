"""Discord OAuth2 login, and the session it establishes.

Flow: ``/login`` bounces the user to Discord with a random ``state``; Discord
returns them to ``/callback`` with a ``code``; we trade it for a token, read who
they are and which guilds they admin, intersect that with the guilds the *bot* is
in, and store the result in the signed session cookie. From then on the session —
not anything the browser sends — decides what they can manage.
"""

from __future__ import annotations

import logging
import secrets

from fastapi import APIRouter, Request, status
from fastapi.responses import RedirectResponse

from dashboard import discord_api
from dashboard.config import get_dashboard_settings
from dashboard.deps import SESSION_GUILDS_KEY, SESSION_USER_KEY, get_current_user
from dashboard.schemas import GuildOut, SessionOut, UserOut

log = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

_STATE_KEY = "oauth_state"


@router.get("/login")
async def login(request: Request) -> RedirectResponse:
    """Begin login: stash a CSRF ``state`` and redirect to Discord's consent page."""
    state = secrets.token_urlsafe(24)
    request.session[_STATE_KEY] = state
    return RedirectResponse(discord_api.authorize_url(state))


@router.get("/callback")
async def callback(request: Request, code: str = "", state: str = "") -> RedirectResponse:
    """Discord redirects here. Validate, build the session, bounce to the app."""
    settings = get_dashboard_settings()
    expected = request.session.pop(_STATE_KEY, None)
    if not code or not state or state != expected:
        return RedirectResponse(f"{settings.frontend_url}/?error=auth")

    try:
        token = await discord_api.exchange_code(code)
        access_token = token["access_token"]
        user = await discord_api.fetch_user(access_token)
        user_guilds = await discord_api.fetch_user_guilds(access_token)
        bot_guild_ids = await discord_api.fetch_bot_guild_ids()
    except Exception:  # network / Discord error — don't leak details to the browser
        log.exception("OAuth callback failed")
        return RedirectResponse(f"{settings.frontend_url}/?error=discord")

    # Guilds the user may manage AND the bot is actually in.
    manageable: dict[str, dict] = {}
    for g in user_guilds:
        if int(g["id"]) in bot_guild_ids and discord_api.manageable(g):
            manageable[str(g["id"])] = {"name": g["name"], "icon": g.get("icon")}

    request.session[SESSION_USER_KEY] = {
        "id": str(user["id"]),
        "username": user["username"],
        "global_name": user.get("global_name"),
        "avatar": user.get("avatar"),
    }
    request.session[SESSION_GUILDS_KEY] = manageable
    return RedirectResponse(settings.frontend_url)


@router.get("/me", response_model=SessionOut)
async def me(request: Request) -> SessionOut:
    """The current session: who you are and which servers you can configure."""
    user = get_current_user(request)
    guilds = request.session.get(SESSION_GUILDS_KEY, {})
    return SessionOut(
        user=UserOut(**user),
        guilds=[
            GuildOut(id=gid, name=g["name"], icon=g.get("icon"))
            for gid, g in guilds.items()
        ],
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request) -> None:
    request.session.clear()
