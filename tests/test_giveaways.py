"""Giveaways: the service contract (create/lookup, toggle entry, due→mark_ended,
entrants, active_for) and the winner-draw helper."""

from __future__ import annotations

from datetime import timedelta

from src.database.base import Base
from src.database.session import engine
from src.modules.giveaways import service
from src.modules.giveaways.cog import _draw


async def _schema() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def _soon():
    return service._now() + timedelta(hours=1)


# ── service contract ─────────────────────────────────────────────────────────

async def test_toggle_entry_enter_then_leave():
    await _schema()
    await service.create(1, 2, 100, "Nitro", 1, _soon(), 9)
    assert await service.toggle_entry(100, 5) == "entered"
    assert await service.toggle_entry(100, 5) == "left"
    assert await service.toggle_entry(999, 5) == "missing"


async def test_due_returns_then_mark_ended_excludes():
    await _schema()
    await service.create(1, 2, 200, "p", 1, service._now() - timedelta(seconds=1), 9)
    due = await service.due()
    assert len(due) == 1
    await service.mark_ended(due[0].id)
    assert await service.due() == []


async def test_entrants_are_unique_and_listed():
    await _schema()
    await service.create(1, 2, 300, "p", 2, _soon(), 9)
    g = await service.get_by_message(300)
    await service.toggle_entry(300, 11)
    await service.toggle_entry(300, 12)
    await service.toggle_entry(300, 11)  # leaves
    assert set(await service.entrants(g.id)) == {12}


async def test_active_for_excludes_ended():
    await _schema()
    guild = 40  # isolated guild id (the shared test DB persists across tests)
    await service.create(guild, 2, 400, "p", 1, _soon(), 9)
    assert len(await service.active_for(guild)) == 1
    g = await service.get_by_message(400)
    await service.mark_ended(g.id)
    assert await service.active_for(guild) == []


# ── winner draw ──────────────────────────────────────────────────────────────

def test_draw_caps_at_entrants_and_returns_a_subset():
    assert _draw([], 3) == []
    assert len(_draw([1, 2, 3], 5)) == 3
    assert set(_draw([1, 2, 3], 2)).issubset({1, 2, 3})
