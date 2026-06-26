"""Styled embed builders. One place defines the bot's look for every message."""

from __future__ import annotations

import discord

from src.core.emojis import Emojis

# The bot's palette. Restyle the whole bot by editing these.
COLOR_SUCCESS = discord.Color.from_str("#43b581")
COLOR_ERROR = discord.Color.from_str("#f04747")
COLOR_WARNING = discord.Color.from_str("#faa61a")
COLOR_INFO = discord.Color.from_str("#5865f2")


def success(description: str, title: str | None = None) -> discord.Embed:
    return discord.Embed(
        title=f"{Emojis.SUCCESS} {title}" if title else None,
        description=description if title else f"{Emojis.SUCCESS} {description}",
        color=COLOR_SUCCESS,
    )


def error(description: str, title: str | None = None) -> discord.Embed:
    return discord.Embed(
        title=f"{Emojis.ERROR} {title}" if title else None,
        description=description if title else f"{Emojis.ERROR} {description}",
        color=COLOR_ERROR,
    )


def warning(description: str, title: str | None = None) -> discord.Embed:
    return discord.Embed(
        title=f"{Emojis.WARNING} {title}" if title else None,
        description=description if title else f"{Emojis.WARNING} {description}",
        color=COLOR_WARNING,
    )


def info(description: str, title: str | None = None) -> discord.Embed:
    return discord.Embed(
        title=title,
        description=description,
        color=COLOR_INFO,
    )
