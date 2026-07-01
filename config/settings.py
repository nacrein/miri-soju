"""Application settings, loaded from environment / .env."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Discord
    bot_token: str = Field(..., alias="BOT_TOKEN")

    # Optional explicit owner id (otherwise taken from the bot application).
    owner_id: int | None = Field(None, alias="OWNER_ID")
    # Optional dev/test guild. When set, slash commands are synced to this guild
    # on startup (instant). Leave unset in production and sync globally via
    # `jsk sync` to avoid the per-restart global sync rate limit.
    dev_guild_id: int | None = Field(None, alias="DEV_GUILD_ID")
    # Comma-separated trusted staff user IDs. Legacy bootstrap: these are always
    # treated as the `staff` tier. Runtime tiers (staff/admin) now live in the
    # `staff_members` table, managed with `,staff promote` / `demote`; env ids are
    # not backfilled into it and resolve purely through the fallback in core/checks.
    staff_ids: str = Field("", alias="STAFF_IDS")

    # Anthropic (AI commands). Empty disables the ,ask command at runtime.
    anthropic_api_key: str = Field("", alias="ANTHROPIC_API_KEY")

    # Database
    database_url: str = Field(..., alias="DATABASE_URL")  # postgresql+asyncpg://user:pass@host/db

    # Engine pool tuning
    db_pool_size: int = Field(10, alias="DB_POOL_SIZE")
    db_max_overflow: int = Field(5, alias="DB_MAX_OVERFLOW")
    db_echo: bool = Field(False, alias="DB_ECHO")  # log all SQL; on for debugging


@lru_cache
def get_settings() -> Settings:
    """Cached so the .env is parsed once per process."""
    return Settings()  # type: ignore[call-arg]
