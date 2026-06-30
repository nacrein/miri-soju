"""Autoroles: the add/remove/list service contract (DB-backed) and the join
listener's role-filtering rule (skip managed/@everyone/above-the-bot)."""

from __future__ import annotations

from src.database.base import Base
from src.database.session import engine
from src.modules.autoroles import service
from src.modules.autoroles.cog import _assignable


async def _schema() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# ── service contract ─────────────────────────────────────────────────────────

async def test_add_is_idempotent_and_remove_reports_rowcount():
    await _schema()
    guild = 700001
    assert await service.add(guild, 11) is True
    assert await service.add(guild, 11) is False      # duplicate ignored by the unique guard
    assert await service.list_roles(guild) == [11]
    assert await service.remove(guild, 11) is True
    assert await service.remove(guild, 11) is False   # already gone


async def test_list_is_scoped_per_guild():
    await _schema()
    await service.add(700002, 1)
    await service.add(700003, 2)
    assert await service.list_roles(700002) == [1]


# ── _assignable filter ───────────────────────────────────────────────────────

class _Role:
    def __init__(self, rid, *, managed=False, default=False, position=1):
        self.id = rid
        self.managed = managed
        self._default = default
        self.position = position

    def is_default(self) -> bool:
        return self._default

    def __lt__(self, other) -> bool:   # discord.Role orders by hierarchy position
        return self.position < other.position

    def __ge__(self, other) -> bool:
        return self.position >= other.position


def _guild(bot_top_position: int = 10):
    from types import SimpleNamespace
    return SimpleNamespace(me=SimpleNamespace(top_role=_Role(99, position=bot_top_position)))


def test_assignable_accepts_a_normal_lower_role():
    assert _assignable(_guild(), _Role(1, position=5)) is True


def test_assignable_rejects_managed_default_and_too_high():
    g = _guild(bot_top_position=10)
    assert _assignable(g, _Role(1, managed=True, position=5)) is False
    assert _assignable(g, _Role(2, default=True, position=5)) is False
    assert _assignable(g, _Role(3, position=20)) is False   # above the bot
