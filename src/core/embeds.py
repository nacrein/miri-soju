"""Styled embed builders. One place defines the bot's look for every message."""

from __future__ import annotations

import discord

from src.core.emojis import Emojis

# The bot's palette, a dusk theme. Restyle the whole bot by editing these.
# Dusk indigo is the signature/neutral color; success, error, and warning are
# dusk-toned variants kept distinct enough to read at a glance.
COLOR_DUSK = discord.Color.from_str("#4C4A7D")     # signature / neutral
COLOR_SUCCESS = discord.Color.from_str("#5F8D7E")  # sage dusk
COLOR_ERROR = discord.Color.from_str("#A05566")    # mauve dusk
COLOR_WARNING = discord.Color.from_str("#C08A4E")  # amber dusk
COLOR_INFO = COLOR_DUSK

# Light footer signature on command embeds. Set BRAND = "" to drop it entirely.
# A cog that sets its own footer overrides this, so functional footers
# (pagination, hints) still win.
BRAND = "Betta"


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
    """The shared modern finish: dusk accent, a timestamp, a light brand footer
    (which any caller can override), and the invoker's author row when given."""
    e = discord.Embed(title=title, description=description, color=color)
    e.timestamp = discord.utils.utcnow()
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
