"""FastAPI application factory.

Mounts every API router under ``/api`` and signs the session cookie. In
production it can also serve the built React frontend (``frontend/dist``) so the
whole thing is one same-origin app; in dev the Vite server proxies ``/api`` here
instead, so this static-serving is skipped.
"""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from dashboard.config import get_dashboard_settings
from dashboard.routers import (
    auth,
    automod,
    guilds,
    leveling,
    moderation,
    prefix,
    serverlog,
    staff,
)
from src.core.cache_sync import publish_guild_changed

_FRONTEND_DIST = Path(__file__).resolve().parent / "frontend" / "dist"

# Config endpoints live under /guilds/<id>/...; a successful write to one means the
# bot's in-process cache for that guild is now stale.
_GUILD_PATH = re.compile(r"/guilds/(\d+)")
_WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def create_app() -> FastAPI:
    settings = get_dashboard_settings()
    app = FastAPI(title="Bot Dashboard", docs_url="/api/docs", openapi_url="/api/openapi.json")

    # Signed, http-only session cookie (Starlette uses itsdangerous under the hood).
    # Secure the cookie automatically when the frontend is served over HTTPS, even
    # if the operator forgot the flag; localhost http stays non-secure for dev.
    https_only = settings.cookie_secure or settings.frontend_url.startswith("https")
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret,
        session_cookie="dash_session",
        same_site="lax",
        https_only=https_only,
        # Authorization (the manageable-guild set) is snapshotted at login, so cap
        # how long a stale snapshot can live — a re-login re-checks Discord. 8 hours.
        max_age=8 * 3600,
    )

    # Only needed if the frontend is served from a *different* origin than this API
    # (otherwise same-origin / the Vite proxy covers it). Credentialed, so the
    # origin must be explicit — never "*".
    # Credentialed CORS: per the Fetch spec "*" isn't a wildcard once credentials
    # are allowed, so enumerate exactly what the API uses.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_url],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type"],
    )

    @app.middleware("http")
    async def _invalidate_bot_cache_after_write(request: Request, call_next):
        """After a successful config write, tell the bot to drop that guild's cache.

        The bot serves config from in-process TTL caches, so a dashboard write would
        otherwise stay invisible for up to the cache TTL. Best-effort and no-op on
        SQLite; never affects the response the user gets."""
        response = await call_next(request)
        if request.method in _WRITE_METHODS and response.status_code < 400:
            match = _GUILD_PATH.search(request.url.path)
            if match:
                await publish_guild_changed(int(match.group(1)))
        return response

    api_routers = (
        auth.router,
        guilds.router,
        leveling.router,
        serverlog.router,
        prefix.router,
        moderation.router,
        automod.router,
        staff.router,
    )
    for router in api_routers:
        app.include_router(router, prefix="/api")

    @app.get("/api/health")
    async def health() -> dict:
        return {"status": "ok"}

    @app.get("/api/meta")
    async def meta() -> dict:
        """Public bot metadata for the landing page (the OAuth app / invite link).

        The client id is the bot's application id, so we can build a real
        "Add to Discord" invite without shipping it into the bundle at build time."""
        client_id = settings.discord_client_id
        invite_url = (
            f"https://discord.com/oauth2/authorize?client_id={client_id}"
            "&permissions=8&scope=bot+applications.commands"
        )
        return {"client_id": client_id, "invite_url": invite_url}

    @app.get("/api/emojis")
    async def emojis() -> dict:
        """The bot's emoji registry, so the website uses Miri's real brand art.

        Returns ``{name: token}`` where token is either a unicode fallback or a
        custom-emoji mention like ``<:bits:123…>``. The frontend renders the custom
        image when an id is present — so uploading art and setting the id in
        ``src/core/emojis.py`` updates the site with no frontend change."""
        from src.core.emojis import Emojis

        return {
            name.lower(): value
            for name, value in vars(Emojis).items()
            if name.isupper() and isinstance(value, str)
        }

    _mount_frontend(app)
    return app


def _mount_frontend(app: FastAPI) -> None:
    """Serve the built SPA if it exists, with index.html fallback for client routes."""
    if not _FRONTEND_DIST.is_dir():
        return

    assets = _FRONTEND_DIST / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    index = _FRONTEND_DIST / "index.html"

    @app.get("/{full_path:path}")
    async def spa(full_path: str) -> FileResponse:
        # A real /api/* path matched earlier and won; one that reaches here doesn't
        # exist, so 404 it instead of masking the error with index.html. Everything
        # else is a client-side route → serve the SPA shell.
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404)
        candidate = _FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index)


app = create_app()
