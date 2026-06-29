"""AutoMod state: the per-guild config plus its word/domain/exemption lists.

One scalar ``automod_config`` row per guild (filter toggles, thresholds, escalation
tiers) and four child tables for the variable-length lists. Defaults are
deliberately safe: a fresh guild is disabled and, once enabled, starts in
``log_only`` (dry-run) mode until an admin turns it off.
"""

from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base, IdMixin, TimestampMixin


class AutomodConfig(Base, TimestampMixin):
    """Per-guild automod settings (one row per guild)."""

    __tablename__ = "automod_config"

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    # ── master ────────────────────────────────────────────────────────────────
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    log_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)  # dry-run
    dm_on_action: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    exempt_mods: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    strike_window_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=24)

    # ── filters: links & invites ───────────────────────────────────────────────
    filter_invites: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    filter_links: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # ── filters: spam & flooding ───────────────────────────────────────────────
    filter_spam: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    spam_count: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    spam_interval: Mapped[int] = mapped_column(Integer, nullable=False, default=5)  # seconds
    duplicate_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=3)

    # ── filters: mass mentions ─────────────────────────────────────────────────
    filter_mentions: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    mention_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    block_everyone: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # ── filters: bad content ───────────────────────────────────────────────────
    filter_words: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    filter_caps: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    caps_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=70)
    caps_min_len: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    filter_emoji: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    emoji_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=10)

    # ── escalation tiers (0/None disables a tier) ──────────────────────────────
    timeout_at: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    timeout_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    timeout2_at: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    timeout2_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    kick_at: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    ban_at: Mapped[int] = mapped_column(Integer, nullable=False, default=5)


class AutomodWord(Base, IdMixin, TimestampMixin):
    """A banned word/phrase, stored normalized + lowercased for direct matching."""

    __tablename__ = "automod_words"
    __table_args__ = (UniqueConstraint("guild_id", "word", name="uq_automodword_guild_word"),)

    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    word: Mapped[str] = mapped_column(String(100), nullable=False)


class AutomodDomain(Base, IdMixin, TimestampMixin):
    """An allowlisted domain that the link filter always permits."""

    __tablename__ = "automod_domains"
    __table_args__ = (UniqueConstraint("guild_id", "domain", name="uq_automoddomain_guild_domain"),)

    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    domain: Mapped[str] = mapped_column(String(100), nullable=False)


class AutomodExemptRole(Base, IdMixin, TimestampMixin):
    """A role whose members the automod never actions."""

    __tablename__ = "automod_exempt_roles"
    __table_args__ = (UniqueConstraint("guild_id", "role_id", name="uq_automodexrole_guild_role"),)

    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    role_id: Mapped[int] = mapped_column(BigInteger, nullable=False)


class AutomodExemptChannel(Base, IdMixin, TimestampMixin):
    """A channel the automod never scans."""

    __tablename__ = "automod_exempt_channels"
    __table_args__ = (UniqueConstraint("guild_id", "channel_id", name="uq_automodexchan_guild_channel"),)

    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
