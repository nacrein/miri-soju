"""Tests for reminder removal: the service rowcount contract and the cog's
remove-by-index path reporting failure when the row vanished mid-operation.
"""

from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace

import pytest
from discord.ext import commands

from src.database.base import Base
from src.database.session import engine
from src.modules.reminder import service
from src.modules.reminder.cog import ReminderCog


async def _schema() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# ── service.remove rowcount contract (DB-backed) ─────────────────────────────

async def test_remove_returns_true_then_false_for_same_row():
    await _schema()
    user = 620001
    await service.add(user, 1, 1, service._now() + timedelta(hours=1), "ping")
    rows = await service.for_user(user)
    assert len(rows) == 1
    # First delete succeeds; a second delete of the gone row reports False.
    assert await service.remove(user, rows[0].id) is True
    assert await service.remove(user, rows[0].id) is False


async def test_remove_does_not_touch_another_users_reminder():
    await _schema()
    owner, other = 620002, 620003
    await service.add(owner, 1, 1, service._now() + timedelta(hours=1), "mine")
    rid = (await service.for_user(owner))[0].id
    # Another user cannot delete it (rowcount 0), and it survives.
    assert await service.remove(other, rid) is False
    assert len(await service.for_user(owner)) == 1


# ── cog remove-by-index: report failure when the row is already gone ─────────

def _fake_ctx():
    sent: list = []

    async def send(*, embed):
        sent.append(embed)

    return SimpleNamespace(author=SimpleNamespace(id=620004), send=send, sent=sent)


async def test_cog_remove_raises_when_row_vanished_between_list_and_delete(monkeypatch):
    # A reminder is listed, but the delivery loop (or a concurrent remove) deletes
    # it before our delete runs, so service.remove returns False.
    async def fake_for_user(uid):
        return [SimpleNamespace(id=555, message="x", remind_at=service._now())]

    async def fake_remove(uid, rid):
        return False

    monkeypatch.setattr(service, "for_user", fake_for_user)
    monkeypatch.setattr(service, "remove", fake_remove)

    cog = ReminderCog.__new__(ReminderCog)  # bypass __init__; no loop needed
    ctx = _fake_ctx()
    with pytest.raises(commands.BadArgument):
        await cog.reminder_remove.callback(cog, ctx, 1)
    assert ctx.sent == []  # never falsely reported success


async def test_cog_remove_reports_success_when_delete_lands(monkeypatch):
    async def fake_for_user(uid):
        return [SimpleNamespace(id=555, message="x", remind_at=service._now())]

    async def fake_remove(uid, rid):
        return True

    monkeypatch.setattr(service, "for_user", fake_for_user)
    monkeypatch.setattr(service, "remove", fake_remove)

    cog = ReminderCog.__new__(ReminderCog)
    ctx = _fake_ctx()
    await cog.reminder_remove.callback(cog, ctx, 1)
    assert len(ctx.sent) == 1
