"""Dashboard settings, loaded from the same ``.env`` the bot uses.

Adds the web-only knobs (Discord OAuth app credentials, the session signing
secret, the frontend origin) on top of the bot's existing settings. The bot
token itself is *reused* from ``config.settings`` — the dashboard makes Bot-auth
REST calls (guild list, roles, channels) with the same identity as the bot.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DashboardSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Discord OAuth2 application (Developer Portal → OAuth2). The client id is the
    # same as the bot's application id; the secret is the OAuth2 client secret.
    discord_client_id: str = Field(..., alias="DISCORD_CLIENT_ID")
    discord_client_secret: str = Field(..., alias="DISCORD_CLIENT_SECRET")

    # Where Discord sends the user back after they authorize. Must be listed as a
    # redirect in the Developer Portal. In dev this points at the Vite dev server,
    # which proxies /api to this backend; in prod it's your real domain.
    oauth_redirect_uri: str = Field(
        "http://localhost:5173/api/auth/callback", alias="OAUTH_REDIRECT_URI"
    )

    # Secret used to sign the session cookie. Generate one with
    # `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
    session_secret: str = Field(..., alias="DASHBOARD_SESSION_SECRET")

    # Where to send the browser after a successful login.
    frontend_url: str = Field("http://localhost:5173", alias="DASHBOARD_FRONTEND_URL")

    # Set cookies with Secure (HTTPS only). Turn on in production.
    cookie_secure: bool = Field(False, alias="DASHBOARD_COOKIE_SECURE")

    # How long a session (and the manageable-guild snapshot taken at login) stays
    # valid before a re-login re-checks Discord. This is the window in which someone
    # whose Manage Server was revoked can still reach the dashboard, so shorten it to
    # tighten revocation (e.g. 7200 = 2h). Default 8h. In seconds.
    session_max_age: int = Field(8 * 3600, alias="DASHBOARD_SESSION_MAX_AGE")


@lru_cache
def get_dashboard_settings() -> DashboardSettings:
    return DashboardSettings()  # type: ignore[call-arg]
