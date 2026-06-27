"""Webhook storage logic. Short ids map to webhook ids; the cog resolves the live hook."""

from __future__ import annotations

import secrets

from src.database.session import get_session
from src.modules.webhook.repository import WebhookRepository


def new_short_id() -> str:
    return secrets.token_hex(3)  # 6 hex chars


async def record(guild_id: int, channel_id: int, webhook_id: int) -> str:
    short = new_short_id()
    async with get_session() as session:
        await WebhookRepository(session).add(guild_id, channel_id, webhook_id, short)
    return short


async def resolve(guild_id: int, short_id: str) -> tuple[int, int] | None:
    """Return (channel_id, webhook_id) for a short id, or None."""
    async with get_session() as session:
        row = await WebhookRepository(session).get(guild_id, short_id)
        return (row.channel_id, row.webhook_id) if row else None


async def all_for(guild_id: int):
    async with get_session() as session:
        return await WebhookRepository(session).list(guild_id)


async def forget(guild_id: int, short_id: str) -> bool:
    async with get_session() as session:
        return await WebhookRepository(session).remove(guild_id, short_id)
