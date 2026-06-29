"""FastAPI application factory.

Mounts every API router under ``/api`` and signs the session cookie. In
production it can also serve the built React frontend (``frontend/dist``) so the
whole thing is one same-origin app; in dev the Vite server proxies ``/api`` here
instead, so this static-serving is skipped.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from dashboard.config import get_dashboard_settings
from dashboard.routers import auth, automod, guilds, leveling, moderation, prefix, serverlog

_FRONTEND_DIST = Path(__file__).resolve().parent / "frontend" / "dist"


def create_app() -> FastAPI:
    settings = get_dashboard_settings()
    app = FastAPI(title="Bot Dashboard", docs_url="/api/docs", openapi_url="/api/openapi.json")

    # Signed, http-only session cookie (Starlette uses itsdangerous under the hood).
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret,
        session_cookie="dash_session",
        same_site="lax",
        https_only=settings.cookie_secure,
        max_age=7 * 24 * 3600,
    )

    # Only needed if the frontend is served from a *different* origin than this API
    # (otherwise same-origin / the Vite proxy covers it). Credentialed, so the
    # origin must be explicit — never "*".
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_url],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    api_routers = (
        auth.router,
        guilds.router,
        leveling.router,
        serverlog.router,
        prefix.router,
        moderation.router,
        automod.router,
    )
    for router in api_routers:
        app.include_router(router, prefix="/api")

    @app.get("/api/health")
    async def health() -> dict:
        return {"status": "ok"}

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
        # API routes are matched earlier; anything else falls through to the SPA,
        # which does its own client-side routing.
        candidate = _FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index)


app = create_app()
