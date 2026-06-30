"""Tests for the dashboard's Discord REST client and wire-contract schemas.

No live Discord and no real HTTP: we stub ``httpx.AsyncClient`` with a fake that
serves staged pages keyed by the ``after`` cursor, so we can prove the guild-list
calls walk *every* page (Finding 1: a bot/user in >200 guilds must not have its
tail silently dropped, or admins of omitted guilds get spurious 403s).

The schema tests pin the snowflake wire contract (Finding 2): numeric-string ids
are accepted, junk is rejected at the boundary as a 422 instead of becoming an
opaque 500 when the router calls ``int()``.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from dashboard import discord_api
from dashboard.schemas import (
    ChannelMultiplierIn,
    IdItemIn,
    LevelingConfigIn,
    LevelRewardIn,
    ModerationConfigIn,
    ServerlogConfigIn,
)

# ── fake httpx layer ──────────────────────────────────────────────────────────


class _FakeResponse:
    def __init__(self, payload: list[dict]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        pass

    def json(self) -> list[dict]:
        return self._payload


class _FakeClient:
    """Serves pages of guild dicts keyed by the ``after`` cursor.

    ``pages`` is the full list of guilds; it hands back ``GUILDS_PAGE_LIMIT`` at a
    time, exactly like Discord, and records every request for assertions.
    """

    def __init__(self, all_guilds: list[dict]) -> None:
        self._all = all_guilds
        self.requests: list[dict] = []

    async def __aenter__(self) -> _FakeClient:
        return self

    async def __aexit__(self, *exc) -> None:
        return None

    async def get(self, url: str, headers=None, params=None) -> _FakeResponse:
        self.requests.append({"url": url, "headers": headers, "params": params})
        after = int((params or {}).get("after", 0))
        limit = (params or {}).get("limit", discord_api.GUILDS_PAGE_LIMIT)
        page = [g for g in self._all if int(g["id"]) > after]
        page.sort(key=lambda g: int(g["id"]))
        return _FakeResponse(page[:limit])


def _make_guilds(n: int, start: int = 1_000_000_000_000_000_000) -> list[dict]:
    # Realistic 19-digit snowflakes so string-vs-int cursor bugs would surface.
    return [{"id": str(start + i), "permissions": "8"} for i in range(n)]


@pytest.fixture(autouse=True)
def _clear_bot_cache():
    discord_api._bot_guilds_cache.clear()
    yield
    discord_api._bot_guilds_cache.clear()


def _patch_client(monkeypatch, all_guilds: list[dict]) -> _FakeClient:
    client = _FakeClient(all_guilds)
    monkeypatch.setattr(discord_api.httpx, "AsyncClient", lambda *a, **k: client)
    monkeypatch.setattr(discord_api, "get_settings", lambda: type("S", (), {"bot_token": "t"})())
    return client


# ── Finding 1: pagination ───────────────────────────────────────────────────


async def test_fetch_bot_guild_ids_single_page(monkeypatch):
    _patch_client(monkeypatch, _make_guilds(3))
    ids = await discord_api.fetch_bot_guild_ids()
    assert len(ids) == 3


async def test_fetch_bot_guild_ids_paginates_past_200(monkeypatch):
    client = _patch_client(monkeypatch, _make_guilds(450))
    ids = await discord_api.fetch_bot_guild_ids()
    # Every guild is returned, not just the first 200.
    assert len(ids) == 450
    # 200 + 200 + 50 => 3 pages.
    assert len(client.requests) == 3
    # Each request after the first advances the cursor to the last id of the prior page.
    assert client.requests[0]["params"]["after"] == "0"
    assert int(client.requests[1]["params"]["after"]) > 0
    assert all(r["params"]["limit"] == discord_api.GUILDS_PAGE_LIMIT for r in client.requests)


async def test_fetch_bot_guild_ids_exact_page_boundary(monkeypatch):
    # Exactly 200 -> a second (empty) request confirms the end; nothing dropped.
    client = _patch_client(monkeypatch, _make_guilds(200))
    ids = await discord_api.fetch_bot_guild_ids()
    assert len(ids) == 200
    assert len(client.requests) == 2


async def test_fetch_bot_guild_ids_is_cached(monkeypatch):
    client = _patch_client(monkeypatch, _make_guilds(3))
    await discord_api.fetch_bot_guild_ids()
    first_call_count = len(client.requests)
    await discord_api.fetch_bot_guild_ids()
    # Second call is served from cache: no new HTTP requests.
    assert len(client.requests) == first_call_count


async def test_fetch_user_guilds_paginates_past_200(monkeypatch):
    client = _patch_client(monkeypatch, _make_guilds(450))
    guilds = await discord_api.fetch_user_guilds("bearer-token")
    assert len(guilds) == 450
    assert len(client.requests) == 3
    # Bearer auth, not bot auth, and dict shape preserved (permissions kept).
    assert client.requests[0]["headers"]["Authorization"] == "Bearer bearer-token"
    assert all("permissions" in g for g in guilds)


# ── Finding 2: snowflake numeric validation ─────────────────────────────────


def test_id_item_accepts_valid_snowflake():
    assert IdItemIn(id="123456789012345678").id == "123456789012345678"


@pytest.mark.parametrize("bad", ["abc", "", "12", "12.5", "  ", "1" * 21, "12345abc"])
def test_id_item_rejects_non_snowflake(bad):
    with pytest.raises(ValidationError):
        IdItemIn(id=bad)


def test_level_reward_rejects_non_numeric_role():
    with pytest.raises(ValidationError):
        LevelRewardIn(level=5, role_id="not-a-number")


def test_channel_multiplier_rejects_non_numeric_channel():
    with pytest.raises(ValidationError):
        ChannelMultiplierIn(channel_id="abc", multiplier=1.5)


def test_optional_snowflakes_accept_none_and_valid():
    assert ModerationConfigIn(jail_role_id=None).jail_role_id is None
    assert ModerationConfigIn(jail_role_id="123456789012345678").jail_role_id == (
        "123456789012345678"
    )
    cfg = ServerlogConfigIn(
        log_channel_id="123456789012345678",
        log_joins=True,
        log_leaves=True,
        log_message_delete=True,
        log_message_edit=True,
        log_mod_actions=True,
    )
    assert cfg.log_channel_id == "123456789012345678"


def test_optional_snowflakes_reject_junk():
    with pytest.raises(ValidationError):
        ModerationConfigIn(jail_role_id="abc")


def test_leveling_config_rejects_non_numeric_announce_channel():
    with pytest.raises(ValidationError):
        LevelingConfigIn(
            enabled=True,
            xp_per_message=10,
            message_cooldown=30,
            announce_mode="channel",
            announce_channel_id="not-numeric",
            level_up_message="gg",
        )
