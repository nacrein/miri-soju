"""AutoMod logic: cached config/list reads, setters, the spam tracker, and the
escalation engine. Mirrors the leveling service (read-through ``TTLCache`` + setters
that invalidate). Discord work is delegated to ``enforcement``; this stays thin.
"""

from __future__ import annotations

import time
from collections import deque
from datetime import datetime, timedelta, timezone

from src.core.cache import TTLCache
from src.database.session import get_session
from src.modules.automod import config as amconfig
from src.modules.automod import enforcement
from src.modules.automod.normalize import WordMatcher, normalize_token
from src.modules.automod.repository import AutomodRepository
from src.modules.moderation import service as mod_service

_NO_CONFIG = object()
_config_cache: TTLCache = TTLCache(ttl_seconds=300)   # guild_id -> AutomodConfig | _NO_CONFIG
_lists_cache: TTLCache = TTLCache(ttl_seconds=300)    # guild_id -> {matcher, word_list, domains, roles, channels}

# In-memory per-(guild,user) spam state — like leveling's _msg_cooldown, never persisted.
# Pruned by the cog's _prune_loop so the dicts can't grow without bound.
_recent_msgs: dict[tuple[int, int], deque] = {}
_recent_text: dict[tuple[int, int], tuple[str, int, float]] = {}


# ── cached reads ───────────────────────────────────────────────────────────────

async def get_config(guild_id: int):
    cached = _config_cache.get(guild_id)
    if cached is not None:
        return None if cached is _NO_CONFIG else cached
    async with get_session() as session:
        cfg = await AutomodRepository(session).get_config(guild_id)
    _config_cache.set(guild_id, cfg if cfg is not None else _NO_CONFIG)
    return cfg


async def get_lists(guild_id: int) -> dict:
    cached = _lists_cache.get(guild_id)
    if cached is not None:
        return cached
    async with get_session() as session:
        repo = AutomodRepository(session)
        words = await repo.list_words(guild_id)
        domains = await repo.list_domains(guild_id)
        roles = await repo.list_exempt_roles(guild_id)
        channels = await repo.list_exempt_channels(guild_id)
    lists = {
        "matcher": WordMatcher(words),
        "word_list": words,
        "domains": set(domains),
        "roles": set(roles),
        "channels": set(channels),
    }
    _lists_cache.set(guild_id, lists)
    return lists


# ── setters (invalidate the config cache) ──────────────────────────────────────

async def _set(guild_id: int, **fields) -> None:
    async with get_session() as session:
        cfg = await AutomodRepository(session).get_or_create_config(guild_id)
        for key, value in fields.items():
            setattr(cfg, key, value)
    _config_cache.invalidate(guild_id)


async def set_enabled(guild_id: int, value: bool) -> None:
    await _set(guild_id, enabled=value)


async def set_log_only(guild_id: int, value: bool) -> None:
    await _set(guild_id, log_only=value)


async def set_dm_on_action(guild_id: int, value: bool) -> None:
    await _set(guild_id, dm_on_action=value)


async def set_exempt_mods(guild_id: int, value: bool) -> None:
    await _set(guild_id, exempt_mods=value)


async def set_strike_window(guild_id: int, hours: int) -> None:
    await _set(guild_id, strike_window_hours=hours)


async def set_filter(guild_id: int, flag: str, value: bool) -> None:
    """Toggle one filter column (e.g. ``filter_invites``) or ``block_everyone``."""
    await _set(guild_id, **{flag: value})


async def set_filters(guild_id: int, **flags: bool) -> None:
    """Set several filter columns at once (the panel's multi-select uses this)."""
    await _set(guild_id, **flags)


async def set_mention_limit(guild_id: int, n: int) -> None:
    await _set(guild_id, mention_limit=n)


async def set_caps(guild_id: int, percent: int, min_len: int) -> None:
    await _set(guild_id, caps_percent=percent, caps_min_len=min_len)


async def set_emoji_limit(guild_id: int, n: int) -> None:
    await _set(guild_id, emoji_limit=n)


async def set_spam(guild_id: int, count: int, interval: int) -> None:
    await _set(guild_id, spam_count=count, spam_interval=interval)


async def set_duplicate_threshold(guild_id: int, n: int) -> None:
    await _set(guild_id, duplicate_threshold=n)


async def set_thresholds(guild_id: int, **tiers) -> None:
    """Set any of timeout_at/timeout_minutes/timeout2_*/kick_at/ban_at."""
    await _set(guild_id, **tiers)


# ── list ops (normalize on store; invalidate the lists cache) ──────────────────

async def add_word(guild_id: int, word: str) -> bool:
    token = normalize_token(word)
    if not token:
        return False
    async with get_session() as session:
        added = await AutomodRepository(session).add_word(guild_id, token)
    _lists_cache.invalidate(guild_id)
    return added


async def remove_word(guild_id: int, word: str) -> bool:
    async with get_session() as session:
        removed = await AutomodRepository(session).remove_word(guild_id, normalize_token(word))
    _lists_cache.invalidate(guild_id)
    return removed


async def list_words(guild_id: int) -> list[str]:
    return (await get_lists(guild_id))["word_list"]


def _clean_domain(domain: str) -> str:
    d = domain.strip().lower().removeprefix("http://").removeprefix("https://")
    return d.split("/")[0]


async def add_domain(guild_id: int, domain: str) -> bool:
    d = _clean_domain(domain)
    if not d:
        return False
    async with get_session() as session:
        added = await AutomodRepository(session).add_domain(guild_id, d)
    _lists_cache.invalidate(guild_id)
    return added


async def remove_domain(guild_id: int, domain: str) -> bool:
    async with get_session() as session:
        removed = await AutomodRepository(session).remove_domain(guild_id, _clean_domain(domain))
    _lists_cache.invalidate(guild_id)
    return removed


async def list_domains(guild_id: int) -> list[str]:
    return sorted((await get_lists(guild_id))["domains"])


async def add_exempt_role(guild_id: int, role_id: int) -> bool:
    async with get_session() as session:
        added = await AutomodRepository(session).add_exempt_role(guild_id, role_id)
    _lists_cache.invalidate(guild_id)
    return added


async def remove_exempt_role(guild_id: int, role_id: int) -> bool:
    async with get_session() as session:
        removed = await AutomodRepository(session).remove_exempt_role(guild_id, role_id)
    _lists_cache.invalidate(guild_id)
    return removed


async def add_exempt_channel(guild_id: int, channel_id: int) -> bool:
    async with get_session() as session:
        added = await AutomodRepository(session).add_exempt_channel(guild_id, channel_id)
    _lists_cache.invalidate(guild_id)
    return added


async def remove_exempt_channel(guild_id: int, channel_id: int) -> bool:
    async with get_session() as session:
        removed = await AutomodRepository(session).remove_exempt_channel(guild_id, channel_id)
    _lists_cache.invalidate(guild_id)
    return removed


# ── spam tracker (pure, in-memory) ─────────────────────────────────────────────

def record_and_check_flood(guild_id: int, user_id: int, count: int, interval: int) -> bool:
    """Record a message and report whether ≥ ``count`` landed within ``interval`` seconds."""
    now = time.monotonic()
    key = (guild_id, user_id)
    dq = _recent_msgs.get(key)
    if dq is None:
        # Size by the max configurable count, so raising spam_count later still works.
        dq = deque(maxlen=amconfig.SPAM_COUNT_MAX)
        _recent_msgs[key] = dq
    dq.append(now)
    while dq and dq[0] < now - interval:
        dq.popleft()
    return len(dq) >= count


def record_and_check_duplicate(guild_id: int, user_id: int, norm_text: str, threshold: int) -> bool:
    """Record the normalized text and report whether it's repeated ≥ ``threshold`` times."""
    key = (guild_id, user_id)
    prev, n, _ = _recent_text.get(key, ("", 0, 0.0))
    n = n + 1 if norm_text and norm_text == prev else 1
    _recent_text[key] = (norm_text, n, time.monotonic())
    return n >= threshold


def prune_spam_state(max_age: float = 600.0) -> None:
    """Drop idle (guild,user) tracker entries so the dicts don't grow without bound."""
    now = time.monotonic()
    for key, dq in list(_recent_msgs.items()):
        while dq and dq[0] < now - max_age:
            dq.popleft()
        if not dq:
            del _recent_msgs[key]
    for key, (_norm, _n, last) in list(_recent_text.items()):
        if last < now - max_age:
            del _recent_text[key]


# ── escalation engine ──────────────────────────────────────────────────────────

async def apply_violation(bot, guild, member, channel, message, violation, cfg, lists) -> None:
    """Record a strike and run the escalated action (or just log it in dry-run mode)."""
    if await enforcement.is_exempt(
        bot, guild, member, cfg, lists["roles"], lists["channels"], channel.id
    ):
        return  # defence in depth — the cog already gated, but never trust a single check
    reason = f"AutoMod ({violation.category}): {violation.reason}"
    since = datetime.now(timezone.utc) - timedelta(hours=cfg.strike_window_hours)

    if cfg.log_only:
        # Dry-run logs but takes no action AND records no strike — otherwise a guild
        # could silently bank strikes and instantly escalate the moment it goes live.
        # Show the action the *next* real strike would trigger.
        would_be = await mod_service.count_recent_cases(guild.id, member.id, "automod", since) + 1
        action, minutes = amconfig.action_for(would_be, cfg)
        await enforcement.log_action(
            bot, guild, member, violation, action, minutes, would_be, dry_run=True
        )
        return

    await mod_service.add_case(guild.id, member.id, bot.user.id, "automod", reason)
    strikes = await mod_service.count_recent_cases(guild.id, member.id, "automod", since)
    action, minutes = amconfig.action_for(strikes, cfg)
    await enforcement.try_delete(message)
    acted = await enforcement.perform(action, minutes, guild, member, reason)
    if cfg.dm_on_action:
        await enforcement.dm_member(member, guild, violation, action, minutes)
    await enforcement.log_action(
        bot, guild, member, violation, action, minutes, strikes, dry_run=False
    )
    return acted
