"""Automod config endpoints — follows the leveling router shape (see leveling.py).

Pattern (same as every module router):
- Depend on ``require_guild`` so the path's guild id is authorized and returned.
- Open ``get_session()`` (it commits on success, rolls back on error).
- Go through the module's *existing* repository — never hand-roll SQL here.
- Convert snowflakes int<->str at the boundary (DB stores int; the wire uses str).
- Mutations return the fresh full config so the client refreshes in one round-trip.

This is the richest router: besides the scalar config it owns four child lists
(words, domains, exempt roles, exempt channels), each with add/remove endpoints.
Every endpoint returns the full ``AutomodConfigOut`` via ``_load``.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from dashboard.deps import require_guild
from dashboard.schemas import (
    AutomodConfigIn,
    AutomodConfigOut,
    IdItemIn,
    StringItemIn,
)
from src.database.session import get_session
from src.modules.automod.repository import AutomodRepository

router = APIRouter(prefix="/guilds/{guild_id}/automod", tags=["automod"])


async def _load(session, guild_id: int) -> AutomodConfigOut:
    repo = AutomodRepository(session)
    cfg = await repo.get_or_create_config(guild_id)
    words = await repo.list_words(guild_id)
    domains = await repo.list_domains(guild_id)
    exempt_roles = await repo.list_exempt_roles(guild_id)
    exempt_channels = await repo.list_exempt_channels(guild_id)
    return AutomodConfigOut(
        enabled=cfg.enabled,
        log_only=cfg.log_only,
        dm_on_action=cfg.dm_on_action,
        exempt_mods=cfg.exempt_mods,
        strike_window_hours=cfg.strike_window_hours,
        filter_invites=cfg.filter_invites,
        filter_links=cfg.filter_links,
        filter_spam=cfg.filter_spam,
        spam_count=cfg.spam_count,
        spam_interval=cfg.spam_interval,
        duplicate_threshold=cfg.duplicate_threshold,
        filter_mentions=cfg.filter_mentions,
        mention_limit=cfg.mention_limit,
        block_everyone=cfg.block_everyone,
        filter_words=cfg.filter_words,
        filter_caps=cfg.filter_caps,
        caps_percent=cfg.caps_percent,
        caps_min_len=cfg.caps_min_len,
        filter_emoji=cfg.filter_emoji,
        emoji_limit=cfg.emoji_limit,
        timeout_at=cfg.timeout_at,
        timeout_minutes=cfg.timeout_minutes,
        timeout2_at=cfg.timeout2_at,
        timeout2_minutes=cfg.timeout2_minutes,
        kick_at=cfg.kick_at,
        ban_at=cfg.ban_at,
        words=words,
        domains=domains,
        exempt_roles=[str(rid) for rid in exempt_roles],
        exempt_channels=[str(cid) for cid in exempt_channels],
    )


@router.get("", response_model=AutomodConfigOut)
async def get_config(guild_id: int = Depends(require_guild)) -> AutomodConfigOut:
    async with get_session() as session:
        return await _load(session, guild_id)


@router.put("", response_model=AutomodConfigOut)
async def update_config(
    body: AutomodConfigIn, guild_id: int = Depends(require_guild)
) -> AutomodConfigOut:
    async with get_session() as session:
        repo = AutomodRepository(session)
        cfg = await repo.get_or_create_config(guild_id)
        cfg.enabled = body.enabled
        cfg.log_only = body.log_only
        cfg.dm_on_action = body.dm_on_action
        cfg.exempt_mods = body.exempt_mods
        cfg.strike_window_hours = body.strike_window_hours
        cfg.filter_invites = body.filter_invites
        cfg.filter_links = body.filter_links
        cfg.filter_spam = body.filter_spam
        cfg.spam_count = body.spam_count
        cfg.spam_interval = body.spam_interval
        cfg.duplicate_threshold = body.duplicate_threshold
        cfg.filter_mentions = body.filter_mentions
        cfg.mention_limit = body.mention_limit
        cfg.block_everyone = body.block_everyone
        cfg.filter_words = body.filter_words
        cfg.filter_caps = body.filter_caps
        cfg.caps_percent = body.caps_percent
        cfg.caps_min_len = body.caps_min_len
        cfg.filter_emoji = body.filter_emoji
        cfg.emoji_limit = body.emoji_limit
        cfg.timeout_at = body.timeout_at
        cfg.timeout_minutes = body.timeout_minutes
        cfg.timeout2_at = body.timeout2_at
        cfg.timeout2_minutes = body.timeout2_minutes
        cfg.kick_at = body.kick_at
        cfg.ban_at = body.ban_at
        return await _load(session, guild_id)


@router.post("/words", response_model=AutomodConfigOut)
async def add_word(
    body: StringItemIn, guild_id: int = Depends(require_guild)
) -> AutomodConfigOut:
    async with get_session() as session:
        repo = AutomodRepository(session)
        await repo.add_word(guild_id, body.value.strip().lower())
        return await _load(session, guild_id)


@router.delete("/words/{word}", response_model=AutomodConfigOut)
async def remove_word(
    word: str, guild_id: int = Depends(require_guild)
) -> AutomodConfigOut:
    async with get_session() as session:
        repo = AutomodRepository(session)
        await repo.remove_word(guild_id, word)
        return await _load(session, guild_id)


@router.post("/domains", response_model=AutomodConfigOut)
async def add_domain(
    body: StringItemIn, guild_id: int = Depends(require_guild)
) -> AutomodConfigOut:
    async with get_session() as session:
        repo = AutomodRepository(session)
        await repo.add_domain(guild_id, body.value.strip().lower())
        return await _load(session, guild_id)


@router.delete("/domains/{domain}", response_model=AutomodConfigOut)
async def remove_domain(
    domain: str, guild_id: int = Depends(require_guild)
) -> AutomodConfigOut:
    async with get_session() as session:
        repo = AutomodRepository(session)
        await repo.remove_domain(guild_id, domain)
        return await _load(session, guild_id)


@router.post("/exempt-roles", response_model=AutomodConfigOut)
async def add_exempt_role(
    body: IdItemIn, guild_id: int = Depends(require_guild)
) -> AutomodConfigOut:
    async with get_session() as session:
        repo = AutomodRepository(session)
        await repo.add_exempt_role(guild_id, int(body.id))
        return await _load(session, guild_id)


@router.delete("/exempt-roles/{role_id}", response_model=AutomodConfigOut)
async def remove_exempt_role(
    role_id: int, guild_id: int = Depends(require_guild)
) -> AutomodConfigOut:
    async with get_session() as session:
        repo = AutomodRepository(session)
        await repo.remove_exempt_role(guild_id, role_id)
        return await _load(session, guild_id)


@router.post("/exempt-channels", response_model=AutomodConfigOut)
async def add_exempt_channel(
    body: IdItemIn, guild_id: int = Depends(require_guild)
) -> AutomodConfigOut:
    async with get_session() as session:
        repo = AutomodRepository(session)
        await repo.add_exempt_channel(guild_id, int(body.id))
        return await _load(session, guild_id)


@router.delete("/exempt-channels/{channel_id}", response_model=AutomodConfigOut)
async def remove_exempt_channel(
    channel_id: int, guild_id: int = Depends(require_guild)
) -> AutomodConfigOut:
    async with get_session() as session:
        repo = AutomodRepository(session)
        await repo.remove_exempt_channel(guild_id, channel_id)
        return await _load(session, guild_id)
