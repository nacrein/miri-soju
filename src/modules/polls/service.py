"""Poll storage logic. No discord here — the cog/view build and edit the message."""

from __future__ import annotations

from src.database.models.poll import Poll
from src.database.session import get_session
from src.modules.polls.repository import PollRepository


async def create(
    guild_id: int, channel_id: int, message_id: int,
    author_id: int, question: str, options: list[str],
) -> None:
    async with get_session() as session:
        await PollRepository(session).create(
            guild_id=guild_id, channel_id=channel_id, message_id=message_id,
            author_id=author_id, question=question, options_text="\n".join(options),
        )


async def get_by_message(message_id: int) -> Poll | None:
    async with get_session() as session:
        return await PollRepository(session).get_by_message(message_id)


async def vote(message_id: int, user_id: int, option_index: int) -> str:
    """Record a vote by the poll's message. Returns ok / closed / missing."""
    async with get_session() as session:
        repo = PollRepository(session)
        poll = await repo.get_by_message(message_id)
        if poll is None:
            return "missing"
        if poll.closed:
            return "closed"
        await repo.vote(poll.id, user_id, option_index)
        return "ok"


async def close(poll_id: int) -> None:
    async with get_session() as session:
        await PollRepository(session).close(poll_id)


async def render_data(message_id: int) -> tuple[Poll, list[str], dict[int, int]] | None:
    """The (poll, option labels, vote counts) needed to (re)draw the poll embed."""
    async with get_session() as session:
        repo = PollRepository(session)
        poll = await repo.get_by_message(message_id)
        if poll is None:
            return None
        counts = await repo.tally(poll.id)
        return poll, poll.options_text.split("\n"), counts
