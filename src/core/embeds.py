"""Styled embed builders. One place defines the bot's look for every message."""

from __future__ import annotations

import discord

from src.core.emojis import Emojis

# The bot's palette, a warm sushi-bar theme. Restyle the whole bot by editing these.
# Warm salmon is the signature/neutral color; success, error, and warning are
# warm-toned variants kept distinct enough to read at a glance.
COLOR_SIGNATURE = discord.Color.from_str("#C56B5C")  # warm salmon - signature / neutral
COLOR_SUCCESS = discord.Color.from_str("#6E9E5E")    # matcha green
COLOR_ERROR = discord.Color.from_str("#B14A52")      # maguro red
COLOR_WARNING = discord.Color.from_str("#D49A3F")    # soy-glaze amber
COLOR_INFO = COLOR_SIGNATURE

# Optional footer signature on command embeds. Empty by default so command embeds
# carry no brand footer (and no timestamp); set BRAND = "Miri" to bring it back.
# A cog that sets its own footer overrides this, so functional footers
# (pagination, hints) still win.
BRAND = ""


def apply_author(embed: discord.Embed, user: discord.abc.User | None) -> discord.Embed:
    """Stamp the invoker onto an embed's author row, unless one is already set.

    This is the signature touch of the house style: every command embed wears the
    person who ran it. It's applied centrally (the bot's Context does it on send),
    so callers rarely call this directly. It never overwrites an author a caller
    set on purpose (e.g. snipe showing the original poster)."""
    if user is not None and embed.author.name is None:
        embed.set_author(name=user.display_name, icon_url=user.display_avatar.url)
    return embed


def _build(
    color: discord.Color,
    title: str | None,
    description: str | None,
    author: discord.abc.User | None = None,
) -> discord.Embed:
    """The shared modern finish: warm salmon accent, the invoker's author row when given,
    and an optional brand footer (off by default; any caller can set its own)."""
    e = discord.Embed(title=title, description=description, color=color)
    apply_author(e, author)
    if BRAND:
        e.set_footer(text=BRAND)
    return e


def success(
    description: str, title: str | None = None, *, author: discord.abc.User | None = None
) -> discord.Embed:
    return _build(
        COLOR_SUCCESS,
        f"{Emojis.SUCCESS} {title}" if title else None,
        description if title else f"{Emojis.SUCCESS} {description}",
        author,
    )


def error(
    description: str, title: str | None = None, *, author: discord.abc.User | None = None
) -> discord.Embed:
    return _build(
        COLOR_ERROR,
        f"{Emojis.ERROR} {title}" if title else None,
        description if title else f"{Emojis.ERROR} {description}",
        author,
    )


def warning(
    description: str, title: str | None = None, *, author: discord.abc.User | None = None
) -> discord.Embed:
    return _build(
        COLOR_WARNING,
        f"{Emojis.WARNING} {title}" if title else None,
        description if title else f"{Emojis.WARNING} {description}",
        author,
    )


def info(
    description: str, title: str | None = None, *, author: discord.abc.User | None = None
) -> discord.Embed:
    return _build(COLOR_INFO, title, description, author)


# ── log records (mod actions + server events) ────────────────────────────────
# Unlike the command-reply builders above, these are *records*: they always carry
# a timestamp (and, where given, an ID footer) so a channel of them reads as a log.
# Their colors come from the same house palette rather than Discord's stock colors.

def audit_log(
    action: str,
    *,
    moderator: discord.abc.User | None = None,
    target: discord.abc.User | None = None,
    reason: str | None = None,
    icon: str | None = None,
    color: discord.Color | None = None,
    fields: list[tuple[str, str]] | None = None,
) -> discord.Embed:
    """A moderation / automod action record: Member, Moderator, Reason, timestamped.

    ``icon`` (an ``Emojis.*``) is prefixed to the title; any extra ``fields`` are
    appended after the standard rows. Defaults to the maguro-red error tone — the
    house equivalent of the dark red these embeds used to hardcode."""
    e = discord.Embed(
        title=f"{icon} {action}" if icon else action,
        color=color or COLOR_ERROR,
    )
    if target is not None:
        e.add_field(name="Member", value=f"{target} (`{target.id}`)", inline=False)
    if moderator is not None:
        e.add_field(name="Moderator", value=str(moderator), inline=False)
    if reason is not None:
        e.add_field(name="Reason", value=reason, inline=False)
    for name, value in fields or []:
        e.add_field(name=name, value=value, inline=False)
    e.timestamp = discord.utils.utcnow()
    return e


def event_log(
    description: str,
    *,
    color: discord.Color,
    author: discord.abc.User | None = None,
    footer: str | None = None,
    fields: list[tuple[str, str]] | None = None,
) -> discord.Embed:
    """A server-audit event record (join / leave / edit / delete): a description-led
    embed in a house color, with an optional member author row and ID footer, always
    timestamped. The caller picks the palette color so the event type stays readable
    at a glance (joins green, leaves red, deletes amber, edits salmon)."""
    e = discord.Embed(description=description, color=color)
    if author is not None:
        e.set_author(name=str(author), icon_url=author.display_avatar.url)
    for name, value in fields or []:
        e.add_field(name=name, value=value, inline=False)
    if footer is not None:
        e.set_footer(text=footer)
    e.timestamp = discord.utils.utcnow()
    return e
