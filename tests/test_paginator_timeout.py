"""Tests for paginator/browser timeout greying and safe close.

The pagers keep the posted message so ``on_timeout`` can grey the controls in
place, and ``CommandBrowser._close`` must not raise if the message is already
gone.
"""

from __future__ import annotations

from types import SimpleNamespace

import discord

from src.core import embeds
from src.core.paginator import CommandBrowser, Paginator


class _FakeResponse:
    status = 404
    reason = "Not Found"


class _FakeMessage:
    """Records edit/delete calls; can be made to raise like a deleted message."""

    def __init__(self, *, raise_on: str | None = None) -> None:
        self.edited_with: dict | None = None
        self.deleted = False
        self._raise_on = raise_on

    async def edit(self, **kwargs):
        if self._raise_on == "edit":
            raise discord.HTTPException(_FakeResponse(), "gone")
        self.edited_with = kwargs

    async def delete(self):
        if self._raise_on == "delete":
            raise discord.HTTPException(_FakeResponse(), "gone")
        self.deleted = True


class _FakeCtx:
    """Minimal ctx whose ``send`` returns a fake message."""

    def __init__(self, message: _FakeMessage) -> None:
        self._message = message
        # A real ctx.author is a Member/User; the author row stamp needs these two.
        self.author = SimpleNamespace(
            id=1, display_name="Tester",
            display_avatar=SimpleNamespace(url="https://example.invalid/a.png"),
        )

    async def send(self, **kwargs):
        return self._message


class _FakeInteractionResponse:
    async def defer(self):
        return None


class _FakeInteraction:
    def __init__(self, message) -> None:
        self.message = message
        self.response = _FakeInteractionResponse()


def _close_button(view: CommandBrowser) -> discord.ui.Button:
    """The ✖ close button is the last one added to the browser."""
    buttons = [c for c in view.children if isinstance(c, discord.ui.Button)]
    return buttons[-1]


async def test_paginator_stores_message_and_greys_on_timeout():
    pages = [embeds.info("a", "A"), embeds.info("b", "B")]
    view = Paginator(1, pages)
    msg = _FakeMessage()
    ctx = _FakeCtx(msg)

    await view.start(ctx)
    assert view.message is msg  # stored for the timeout hook

    await view.on_timeout()
    assert all(c.disabled for c in view.children)
    assert msg.edited_with is not None  # message was edited to show greyed buttons


async def test_paginator_timeout_swallows_http_error():
    view = Paginator(1, [embeds.info("a", "A"), embeds.info("b", "B")])
    view.message = _FakeMessage(raise_on="edit")
    await view.on_timeout()  # must not raise even though edit fails


async def test_command_browser_timeout_greys_stored_message():
    view = CommandBrowser(1, [], "Cat", ",")
    msg = _FakeMessage()
    view.message = msg
    await view.on_timeout()
    assert all(c.disabled for c in view.children)
    assert msg.edited_with is not None


async def test_command_browser_close_swallows_already_deleted():
    view = CommandBrowser(1, [], "Cat", ",")
    interaction = _FakeInteraction(_FakeMessage(raise_on="delete"))
    await _close_button(view).callback(interaction)  # must not raise
    assert view.is_finished()


async def test_command_browser_close_deletes_message():
    view = CommandBrowser(1, [], "Cat", ",")
    msg = _FakeMessage()
    interaction = _FakeInteraction(msg)
    await _close_button(view).callback(interaction)
    assert msg.deleted is True
    assert view.is_finished()
