"""DB-backed tests for the one-time economy rules agreement gate.

Cover the service-level agreement record/lookup (and its in-memory cache), the
"I agree" button recording acceptance, and the embed text. The cog's ``cog_check``
gate itself is exercised live; here we test the pieces it composes. Uses the test
SQLite engine via the same ``_schema()`` pattern as the other DB-backed tests.
"""

from __future__ import annotations

from types import SimpleNamespace

import discord

from src.database.base import Base
from src.database.session import engine
from src.modules.economy import service
from src.modules.economy.agreement import AgreementView, agreement_embed


async def _schema() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


class _FakeResponse:
    def __init__(self) -> None:
        self.edited: dict | None = None

    async def edit_message(self, **kwargs) -> None:
        self.edited = kwargs


async def test_has_agreed_is_false_until_recorded():
    await _schema()
    uid = 90_001
    assert await service.has_agreed(uid) is False
    await service.record_agreement(uid)
    assert await service.has_agreed(uid) is True


async def test_record_agreement_is_idempotent():
    await _schema()
    uid = 90_002
    await service.record_agreement(uid)
    await service.record_agreement(uid)  # second call must not raise or re-stamp
    assert await service.has_agreed(uid) is True


async def test_agree_button_records_and_stops():
    await _schema()
    uid = 90_003
    view = AgreementView(uid, invoker=SimpleNamespace(id=uid))
    interaction = SimpleNamespace(user=SimpleNamespace(id=uid), response=_FakeResponse())
    button = next(c for c in view.children if isinstance(c, discord.ui.Button))
    await button.callback(interaction)
    assert await service.has_agreed(uid) is True
    assert view.is_finished()
    assert interaction.response.edited is not None  # the prompt was edited to a confirmation


def test_agreement_embed_states_the_rules():
    description = agreement_embed().description
    assert "I agree" in description
    assert "alt accounts" in description
