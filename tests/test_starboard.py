"""Starboard: the cached-config service (channel enables, threshold clamp, emoji,
self-star, disable, summary), the entry upsert/get/delete bookkeeping, and the board
post's text/embed rendering."""

from __future__ import annotations

from types import SimpleNamespace

from src.database.base import Base
from src.database.session import engine
from src.modules.starboard import service
from src.modules.starboard.cog import board_embed, board_text


async def _schema() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    service._config_cache.clear()


# ── config service ───────────────────────────────────────────────────────────

async def test_channel_enables_and_summary_defaults():
    await _schema()
    guild = 730001
    assert (await service.get_summary(guild))["enabled"] is False
    await service.set_channel(guild, 88)
    s = await service.get_summary(guild)
    assert s["enabled"] is True and s["channel_id"] == 88
    assert s["threshold"] == 3 and s["star_emoji"] == "⭐"


async def test_threshold_is_clamped():
    await _schema()
    guild = 730002
    await service.set_channel(guild, 1)
    assert await service.set_threshold(guild, 0) == service.MIN_THRESHOLD
    assert await service.set_threshold(guild, 999) == service.MAX_THRESHOLD
    assert await service.set_threshold(guild, 5) == 5


async def test_emoji_selfstar_and_disable():
    await _schema()
    guild = 730003
    await service.set_channel(guild, 1)
    await service.set_emoji(guild, "🌟")
    await service.set_self_star(guild, True)
    s = await service.get_summary(guild)
    assert s["star_emoji"] == "🌟" and s["self_star"] is True
    await service.disable(guild)
    assert (await service.get_summary(guild))["enabled"] is False


# ── entry bookkeeping ────────────────────────────────────────────────────────

async def test_entry_upsert_updates_in_place():
    await _schema()
    guild = 730004
    await service.upsert_entry(guild, message_id=10, board_message_id=20, star_count=3)
    entry = await service.get_entry(guild, 10)
    assert entry.board_message_id == 20 and entry.star_count == 3
    await service.upsert_entry(guild, message_id=10, board_message_id=20, star_count=7)
    assert (await service.get_entry(guild, 10)).star_count == 7
    await service.delete_entry(guild, 10)
    assert await service.get_entry(guild, 10) is None


# ── board rendering ──────────────────────────────────────────────────────────

def _msg():
    return SimpleNamespace(
        content="hello world",
        author=SimpleNamespace(display_name="Nick", display_avatar=SimpleNamespace(url="a")),
        jump_url="https://discord.com/x",
        attachments=[],
        channel=SimpleNamespace(mention="#general"),
        created_at=None,
    )


def test_board_text_and_embed():
    msg = _msg()
    assert board_text(msg, 5, "⭐") == "⭐ **5** · #general"
    e = board_embed(msg)
    assert e.author.name == "Nick"
    source = next(f for f in e.fields if f.name == "Source")
    assert "Jump" in source.value
