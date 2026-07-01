"""Data access for polls and votes."""

from __future__ import annotations

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models.poll import Poll, PollVote


class PollRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self, *, guild_id: int, channel_id: int, message_id: int,
        author_id: int, question: str, options_text: str,
    ) -> Poll:
        poll = Poll(
            guild_id=guild_id, channel_id=channel_id, message_id=message_id,
            author_id=author_id, question=question, options_text=options_text,
        )
        self.session.add(poll)
        await self.session.flush()
        return poll

    async def get_by_message(self, message_id: int) -> Poll | None:
        stmt = select(Poll).where(Poll.message_id == message_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def close(self, poll_id: int) -> None:
        await self.session.execute(
            update(Poll).where(Poll.id == poll_id).values(closed=True)
        )

    async def vote(self, poll_id: int, user_id: int, option_index: int) -> None:
        """One vote per user: replace any previous choice."""
        await self.session.execute(delete(PollVote).where(
            PollVote.poll_id == poll_id, PollVote.user_id == user_id
        ))
        self.session.add(
            PollVote(poll_id=poll_id, user_id=user_id, option_index=option_index)
        )

    async def tally(self, poll_id: int) -> dict[int, int]:
        stmt = (
            select(PollVote.option_index, func.count())
            .where(PollVote.poll_id == poll_id)
            .group_by(PollVote.option_index)
        )
        return {idx: count for idx, count in (await self.session.execute(stmt)).all()}
