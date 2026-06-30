"""Request/response models for the API — the single source of the wire contract.

Conventions:
- **Every Discord snowflake (guild/role/channel/user id) is a string**, in and out.
  They're 64-bit and would lose precision as a JSON number in the browser.
- Validation ranges are *imported from the bot's own config modules* so the web
  forms and the ``,`` commands can never drift (e.g. leveling's RATE_MIN/MAX).
- ``*Out`` models are read shapes; ``*In`` models are write shapes.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

from src.modules.automod import config as am
from src.modules.leveling.config import (
    COOLDOWN_MAX,
    COOLDOWN_MIN,
    MESSAGE_MAX,
    RATE_MAX,
    RATE_MIN,
)

# A Discord snowflake on the wire: a 17–20 digit numeric string. Constraining it
# here rejects junk like {"id": "abc"} with a 422 at the boundary instead of
# letting int() blow up into an opaque 500 in the router.
SnowflakeStr = Annotated[str, Field(pattern=r"^\d{17,20}$")]

# ── identity / guild discovery ───────────────────────────────────────────────


class UserOut(BaseModel):
    id: str
    username: str
    global_name: str | None = None
    avatar: str | None = None


class GuildOut(BaseModel):
    id: str
    name: str
    icon: str | None = None


class RoleOut(BaseModel):
    id: str
    name: str
    color: int = 0
    managed: bool = False


class ChannelOut(BaseModel):
    id: str
    name: str


class GuildMetaOut(BaseModel):
    """Roles + text channels for populating the config dropdowns."""

    guild: GuildOut
    roles: list[RoleOut]
    channels: list[ChannelOut]


class SessionOut(BaseModel):
    user: UserOut
    guilds: list[GuildOut]


# ── leveling ─────────────────────────────────────────────────────────────────


class LevelRewardOut(BaseModel):
    level: int
    role_id: str


class LevelRewardIn(BaseModel):
    level: int = Field(..., ge=1, le=1000)
    role_id: SnowflakeStr


class ChannelMultiplierOut(BaseModel):
    channel_id: str
    multiplier: float


class ChannelMultiplierIn(BaseModel):
    channel_id: SnowflakeStr
    multiplier: float = Field(..., ge=0.0, le=10.0)


class LevelingConfigOut(BaseModel):
    enabled: bool
    xp_per_message: int
    message_cooldown: int
    announce_mode: str
    announce_channel_id: str | None = None
    level_up_message: str
    rewards: list[LevelRewardOut]
    multipliers: list[ChannelMultiplierOut]


class LevelingConfigIn(BaseModel):
    enabled: bool
    xp_per_message: int = Field(..., ge=RATE_MIN, le=RATE_MAX)
    message_cooldown: int = Field(..., ge=COOLDOWN_MIN, le=COOLDOWN_MAX)
    announce_mode: Literal["here", "dm", "channel"]
    announce_channel_id: SnowflakeStr | None = None
    level_up_message: str = Field(..., min_length=1, max_length=MESSAGE_MAX)

    @model_validator(mode="after")
    def _channel_required_for_channel_mode(self) -> LevelingConfigIn:
        # 'channel' mode without a channel would silently fall back to the trigger
        # channel — reject it so the client fixes the form instead of saving a no-op.
        if self.announce_mode == "channel" and not self.announce_channel_id:
            raise ValueError("announce_channel_id is required when announce_mode is 'channel'")
        return self


# ── serverlog (stored on GuildConfig) ────────────────────────────────────────


class ServerlogConfigOut(BaseModel):
    log_channel_id: str | None = None
    log_joins: bool
    log_leaves: bool
    log_message_delete: bool
    log_message_edit: bool
    log_mod_actions: bool


class ServerlogConfigIn(BaseModel):
    log_channel_id: SnowflakeStr | None = None
    log_joins: bool
    log_leaves: bool
    log_message_delete: bool
    log_message_edit: bool
    log_mod_actions: bool


# ── prefix (stored on GuildConfig) ───────────────────────────────────────────


class PrefixOut(BaseModel):
    prefix: str | None = None
    default: str


class PrefixIn(BaseModel):
    # None resets to the global default; otherwise 1–8 non-space chars.
    prefix: str | None = Field(None, min_length=1, max_length=8)


# ── moderation ───────────────────────────────────────────────────────────────


class ModerationConfigOut(BaseModel):
    jail_role_id: str | None = None


class ModerationConfigIn(BaseModel):
    jail_role_id: SnowflakeStr | None = None


# ── automod ──────────────────────────────────────────────────────────────────


class AutomodConfigOut(BaseModel):
    enabled: bool
    log_only: bool
    dm_on_action: bool
    exempt_mods: bool
    strike_window_hours: int
    filter_invites: bool
    filter_links: bool
    filter_spam: bool
    spam_count: int
    spam_interval: int
    duplicate_threshold: int
    filter_mentions: bool
    mention_limit: int
    block_everyone: bool
    filter_words: bool
    filter_caps: bool
    caps_percent: int
    caps_min_len: int
    filter_emoji: bool
    emoji_limit: int
    timeout_at: int
    timeout_minutes: int
    timeout2_at: int
    timeout2_minutes: int
    kick_at: int
    ban_at: int
    words: list[str]
    domains: list[str]
    exempt_roles: list[str]
    exempt_channels: list[str]


class AutomodConfigIn(BaseModel):
    """Scalar automod settings. Lists are managed via their own endpoints."""

    enabled: bool
    log_only: bool
    dm_on_action: bool
    exempt_mods: bool
    strike_window_hours: int = Field(..., ge=am.WINDOW_MIN, le=am.WINDOW_MAX)
    filter_invites: bool
    filter_links: bool
    filter_spam: bool
    spam_count: int = Field(..., ge=am.SPAM_COUNT_MIN, le=am.SPAM_COUNT_MAX)
    spam_interval: int = Field(..., ge=am.SPAM_INTERVAL_MIN, le=am.SPAM_INTERVAL_MAX)
    duplicate_threshold: int = Field(..., ge=am.DUP_MIN, le=am.DUP_MAX)
    filter_mentions: bool
    mention_limit: int = Field(..., ge=am.MENTION_MIN, le=am.MENTION_MAX)
    block_everyone: bool
    filter_words: bool
    filter_caps: bool
    caps_percent: int = Field(..., ge=am.CAPS_PCT_MIN, le=am.CAPS_PCT_MAX)
    caps_min_len: int = Field(..., ge=am.CAPS_LEN_MIN, le=am.CAPS_LEN_MAX)
    filter_emoji: bool
    emoji_limit: int = Field(..., ge=am.EMOJI_MIN, le=am.EMOJI_MAX)
    timeout_at: int = Field(..., ge=am.STRIKE_MIN, le=am.STRIKE_MAX)
    timeout_minutes: int = Field(..., ge=am.MINUTES_MIN, le=am.MINUTES_MAX)
    timeout2_at: int = Field(..., ge=am.STRIKE_MIN, le=am.STRIKE_MAX)
    timeout2_minutes: int = Field(..., ge=am.MINUTES_MIN, le=am.MINUTES_MAX)
    kick_at: int = Field(..., ge=am.STRIKE_MIN, le=am.STRIKE_MAX)
    ban_at: int = Field(..., ge=am.STRIKE_MIN, le=am.STRIKE_MAX)


class StringItemIn(BaseModel):
    """A word or domain to add to an automod list."""

    value: str = Field(..., min_length=1, max_length=100)


class IdItemIn(BaseModel):
    """A role or channel id to add to an automod exemption list."""

    id: SnowflakeStr
