"""Stateless message scanning: turn a message + config into a Violation, or None.

Pure logic (a ``MessageView`` of the bits we need, never a live ``discord.Message``)
so it unit-tests without Discord. Spam/flood and duplicate detection are *stateful*
and live in the service tracker, not here. First matching filter wins; the order
runs cheap/high-signal checks first and short-circuits.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

from src.modules.automod import normalize
from src.modules.automod.normalize import WordMatcher

_INVITE_RE = re.compile(r"(?:discord\.gg|discord(?:app)?\.com/invite|discord\.me)/\S+", re.IGNORECASE)
_URL_RE = re.compile(r"https?://[^\s<>]+", re.IGNORECASE)
_INVITE_HOSTS = {"discord.gg", "discord.com", "discordapp.com", "discord.me"}


@dataclass(frozen=True)
class Violation:
    category: str   # invite | link | mention | everyone | word | caps | emoji
    reason: str


@dataclass
class MessageView:
    """The message facts the filters need (built by the cog from a real message)."""

    content: str
    mention_count: int            # distinct user + role mentions
    mentions_everyone: bool       # the @everyone/@here text is present
    author_can_mention_everyone: bool


def _external_hosts(content: str):
    for url in _URL_RE.findall(content):
        host = (urlparse(url).hostname or "").lower()
        if host:
            yield host


def _is_allowed(host: str, allowed_domains: set[str]) -> bool:
    if host in _INVITE_HOSTS:  # Discord's own links are governed by the invite filter
        return True
    return any(host == d or host.endswith("." + d) for d in allowed_domains)


def scan_static(
    view: MessageView, cfg, matcher: WordMatcher | None, allowed_domains: set[str]
) -> Violation | None:
    content = view.content

    if cfg.filter_mentions:
        if cfg.block_everyone and view.mentions_everyone and not view.author_can_mention_everyone:
            return Violation("everyone", "used @everyone/@here without permission")
        if view.mention_count > cfg.mention_limit:
            return Violation("mention", f"{view.mention_count} mentions (limit {cfg.mention_limit})")

    if cfg.filter_invites and _INVITE_RE.search(content):
        return Violation("invite", "posted a Discord invite link")

    if cfg.filter_links:
        for host in _external_hosts(content):
            if not _is_allowed(host, allowed_domains):
                return Violation("link", f"posted a link to {host}")

    if cfg.filter_words and matcher is not None and matcher.matches(content):
        return Violation("word", "posted a blocked word")

    if cfg.filter_caps:
        stripped = normalize.strip_code(content)
        if len(stripped) >= cfg.caps_min_len and normalize.caps_ratio(stripped) * 100 >= cfg.caps_percent:
            return Violation("caps", "excessive capital letters")

    if cfg.filter_emoji and normalize.count_emojis(content) > cfg.emoji_limit:
        return Violation("emoji", f"too many emoji (limit {cfg.emoji_limit})")

    return None
