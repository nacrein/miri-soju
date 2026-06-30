"""Polls: the vote service (single-vote-per-user, closed gating, tally) and the
tally-bar rendering."""

from __future__ import annotations

from src.database.base import Base
from src.database.session import engine
from src.modules.polls import service
from src.modules.polls.views import _bar, poll_embed


async def _schema() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# ── vote service ─────────────────────────────────────────────────────────────

async def test_vote_is_one_per_user_and_changeable():
    await _schema()
    await service.create(1, 2, 100, 9, "Color?", ["Red", "Blue"])
    assert await service.vote(100, 5, 0) == "ok"
    assert await service.vote(100, 6, 0) == "ok"
    assert await service.vote(100, 5, 1) == "ok"  # user 5 changes their vote
    _poll, options, counts = await service.render_data(100)
    assert options == ["Red", "Blue"]
    assert counts == {0: 1, 1: 1}  # user 6 -> Red, user 5 -> Blue


async def test_vote_on_missing_and_closed():
    await _schema()
    await service.create(1, 2, 200, 9, "Q?", ["A", "B"])
    assert await service.vote(999, 5, 0) == "missing"
    poll = await service.get_by_message(200)
    await service.close(poll.id)
    assert await service.vote(200, 5, 0) == "closed"


# ── rendering ────────────────────────────────────────────────────────────────

def test_bar_scales_with_percentage():
    assert _bar(0) == "▱" * 10
    assert _bar(100) == "▰" * 10
    assert _bar(50).count("▰") == 5


def test_poll_embed_shows_counts_and_closed_state():
    from types import SimpleNamespace
    poll = SimpleNamespace(question="Best?", closed=True)
    e = poll_embed(poll, ["A", "B"], {0: 3, 1: 1})
    assert "Best?" in e.title
    assert "Closed" in e.description and "3" in e.description
