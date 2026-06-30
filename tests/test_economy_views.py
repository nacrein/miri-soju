"""Tests for the interactive economy panels: re-bet, profile hub, vault/generator
panels, and the give/steal confirm. Button callbacks are driven with fake
interactions; money-touching paths use the test SQLite engine."""

from __future__ import annotations

from types import SimpleNamespace

import discord

from src.core import embeds
from src.database.base import Base
from src.database.session import engine, get_session
from src.modules.economy import service
from src.modules.economy import views as econ_views
from src.modules.economy.repository import EconomyRepository


async def _schema() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def _fund(user_id: int, wallet: int) -> None:
    async with get_session() as session:
        player = await EconomyRepository(session).get_or_create(user_id)
        player.wallet = wallet


def _user(uid: int) -> SimpleNamespace:
    return SimpleNamespace(id=uid, display_name="Tester")


class _FakeResponse:
    def __init__(self) -> None:
        self.edited: dict | None = None
        self.sent: dict | None = None
        self.deferred = False

    async def edit_message(self, **kwargs) -> None:
        self.edited = kwargs

    async def send_message(self, **kwargs) -> None:
        self.sent = kwargs

    async def defer(self) -> None:
        self.deferred = True


class _FakeInteraction:
    def __init__(self, uid: int) -> None:
        self.user = _user(uid)
        self.response = _FakeResponse()


def _button(view: discord.ui.View, label: str) -> discord.ui.Button:
    return next(c for c in view.children if isinstance(c, discord.ui.Button) and c.label == label)


# ── shared result builders ───────────────────────────────────────────────────

async def test_play_coinflip_returns_an_embed():
    await _schema()
    uid = 95_001
    await _fund(uid, 1000)
    result = await econ_views.play_coinflip(uid, 100, "heads")
    assert isinstance(result, discord.Embed)


# ── re-bet ────────────────────────────────────────────────────────────────────

async def test_rebet_again_and_double_replay_with_right_amounts():
    seen: list[int] = []

    async def replay(amount: int) -> discord.Embed:
        seen.append(amount)
        return embeds.success("rolled")

    view = econ_views.RebetView(1, 100, replay, invoker=_user(1))
    await _button(view, "Play again").callback(_FakeInteraction(1))
    view._last = 0.0  # bypass the debounce for the test's second click
    await _button(view, "Double").callback(_FakeInteraction(1))
    assert seen == [100, 200]


async def test_rebet_insufficient_funds_disables_and_stops():
    async def replay(amount: int) -> discord.Embed:
        raise service.EconomyError("Not enough bits.")

    view = econ_views.RebetView(1, 100, replay, invoker=_user(1))
    interaction = _FakeInteraction(1)
    await _button(view, "Play again").callback(interaction)
    assert view.is_finished()
    assert all(c.disabled for c in view.children)
    assert interaction.response.edited is not None


# ── vault / generator ─────────────────────────────────────────────────────────

async def test_vault_upgrade_without_funds_warns():
    await _schema()
    uid = 95_020
    view = econ_views.VaultView(_user(uid), invoker=_user(uid))
    interaction = _FakeInteraction(uid)
    await _button(view, "Upgrade").callback(interaction)
    assert interaction.response.sent is not None  # ephemeral error, no edit
    assert interaction.response.edited is None


async def test_generator_refresh_renders():
    await _schema()
    uid = 95_021
    view = econ_views.GeneratorView(_user(uid), invoker=_user(uid))
    interaction = _FakeInteraction(uid)
    await _button(view, "Refresh").callback(interaction)
    assert interaction.response.edited is not None


# ── confirm gate ──────────────────────────────────────────────────────────────

async def test_confirm_runs_action_then_stops():
    ran: list[bool] = []

    async def action() -> discord.Embed:
        ran.append(True)
        return embeds.success("done")

    view = econ_views.ConfirmView(1, action, invoker=_user(1))
    interaction = _FakeInteraction(1)
    await _button(view, "Confirm").callback(interaction)
    assert ran == [True]
    assert view.is_finished()
    assert interaction.response.edited is not None


async def test_confirm_cancel_skips_action():
    ran: list[bool] = []

    async def action() -> discord.Embed:
        ran.append(True)
        return embeds.success("done")

    view = econ_views.ConfirmView(1, action, invoker=_user(1))
    interaction = _FakeInteraction(1)
    await _button(view, "Cancel").callback(interaction)
    assert ran == []
    assert view.is_finished()


def test_confirm_label_is_customizable():
    view = econ_views.ConfirmView(1, None, invoker=_user(1), confirm_label="Attempt")
    assert _button(view, "Attempt") is not None
