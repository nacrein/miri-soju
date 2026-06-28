"""Tests for the leaderboard menu and the shared ranked-list renderer.

No live Discord: we call ``rankings.ranked_list`` directly and construct the menu
view to assert on its dropdown and invoker lock.
"""

from __future__ import annotations

from types import SimpleNamespace

import discord

from src.core import rankings
from src.core.emojis import Emojis
from src.modules.leaderboard.views import LeaderboardMenu


class _FakeGuild:
    def __init__(self, names: dict[int, str]) -> None:
        self._names = names

    def get_member(self, uid: int):
        name = self._names.get(uid)
        return SimpleNamespace(display_name=name) if name else None


_USER = SimpleNamespace(
    id=1, display_name="nacrein", display_avatar=SimpleNamespace(url="https://e/a.png")
)


# ── the shared renderer ──────────────────────────────────────────────────────

def test_top_three_wear_medals_then_plain_ranks():
    guild = _FakeGuild({1: "alice", 2: "bob", 3: "carol", 4: "dave"})
    entries = [(1, "100"), (2, "90"), (3, "80"), (4, "70")]
    e = rankings.ranked_list(guild, entries, "Net Worth")
    lines = e.description.splitlines()
    assert lines[0].startswith(f"{Emojis.MEDAL_GOLD} **alice**")
    assert lines[1].startswith(f"{Emojis.MEDAL_SILVER} **bob**")
    assert lines[2].startswith(f"{Emojis.MEDAL_BRONZE} **carol**")
    assert lines[3].startswith("`#4` **dave**")


def test_title_footer_and_author_stamp():
    e = rankings.ranked_list(
        _FakeGuild({1: "alice"}), [(1, "100")], "Voice Time",
        author=_USER, footer="Global · across every server",
    )
    assert e.title == f"{Emojis.TROPHY} Voice Time"
    assert e.footer.text == "Global · across every server"
    assert e.author.name == "nacrein"  # stamped so it survives edit_message redraws


def test_unknown_member_falls_back_to_id():
    e = rankings.ranked_list(_FakeGuild({}), [(999, "5")], "Net Worth")
    assert "User 999" in e.description


def test_empty_board_uses_the_custom_message():
    e = rankings.ranked_list(_FakeGuild({}), [], "Levels", empty="No ranked members yet.")
    assert "No ranked members yet." in e.description


# ── the menu view ────────────────────────────────────────────────────────────

def test_menu_offers_the_three_global_boards_with_no_default():
    menu = LeaderboardMenu(1, _FakeGuild({}), _USER)
    selects = [c for c in menu.children if isinstance(c, discord.ui.Select)]
    assert len(selects) == 1
    assert {o.value for o in selects[0].options} == {"networth", "voice", "generator"}
    assert not any(o.default for o in selects[0].options)  # landing state: nothing pre-picked


def test_landing_card_lists_the_boards():
    menu = LeaderboardMenu(1, _FakeGuild({}), _USER)
    e = menu._landing()
    assert "Leaderboards" in e.title
    for label in ("Net Worth", "Voice Time", "Generators"):
        assert label in e.description


def test_menu_marks_the_chosen_board_as_default():
    menu = LeaderboardMenu(1, _FakeGuild({}), _USER, board="voice")
    select = next(c for c in menu.children if isinstance(c, discord.ui.Select))
    assert next(o for o in select.options if o.default).value == "voice"


class _FakeResponse:
    def __init__(self) -> None:
        self.sent = None

    async def send_message(self, *args, **kwargs) -> None:
        self.sent = (args, kwargs)


def _interaction(uid: int):
    return SimpleNamespace(user=SimpleNamespace(id=uid), response=_FakeResponse())


async def test_menu_is_locked_to_the_invoker():
    menu = LeaderboardMenu(1, _FakeGuild({}), _USER)
    intruder = _interaction(2)
    assert await menu.interaction_check(intruder) is False
    assert intruder.response.sent[1].get("ephemeral") is True
    assert await menu.interaction_check(_interaction(1)) is True
