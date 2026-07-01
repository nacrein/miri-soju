"""Giveaway storage logic. No discord here — the cog draws winners and posts."""

from __future__ import annotations

from datetime import UTC, datetime

from src.database.models.giveaway import Giveaway
from src.database.session import get_session
from src.modules.giveaways.repository import GiveawayRepository


def _now() -> datetime:
    return datetime.now(UTC)


async def create(
    guild_id: int, channel_id: int, message_id: int,
    prize: str, winners: int, ends_at: datetime, host_id: int,
) -> None:
    async with get_session() as session:
        await GiveawayRepository(session).create(
            guild_id=guild_id, channel_id=channel_id, message_id=message_id,
            prize=prize, winners=winners, ends_at=ends_at, host_id=host_id,
        )


async def get_by_message(message_id: int) -> Giveaway | None:
    async with get_session() as session:
        return await GiveawayRepository(session).get_by_message(message_id)


async def toggle_entry(message_id: int, user_id: int) -> str:
    """Enter or leave by clicking the button. Returns one of
    entered / left / ended / missing for the ephemeral reply."""
    async with get_session() as session:
        repo = GiveawayRepository(session)
        g = await repo.get_by_message(message_id)
        if g is None:
            return "missing"
        if g.ended:
            return "ended"
        if await repo.has_entry(g.id, user_id):
            await repo.remove_entry(g.id, user_id)
            return "left"
        await repo.add_entry(g.id, user_id)
        return "entered"


async def due() -> list[Giveaway]:
    async with get_session() as session:
        return await GiveawayRepository(session).due(_now())


async def active_for(guild_id: int) -> list[Giveaway]:
    async with get_session() as session:
        return await GiveawayRepository(session).active_for(guild_id)


async def mark_ended(giveaway_id: int) -> None:
    async with get_session() as session:
        await GiveawayRepository(session).mark_ended(giveaway_id)


async def entrants(giveaway_id: int) -> list[int]:
    async with get_session() as session:
        return await GiveawayRepository(session).entrants(giveaway_id)
