"""Welcome/goodbye: the config service (set-channel-enables, custom message, disable,
resolve with defaults, per-guild summary) and the placeholder renderer."""

from __future__ import annotations

from types import SimpleNamespace

from src.database.base import Base
from src.database.session import engine
from src.modules.welcome import service
from src.modules.welcome.cog import render


async def _schema() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    service._config_cache.clear()


# ── service contract ─────────────────────────────────────────────────────────

async def test_set_channel_enables_and_resolve_returns_default_template():
    await _schema()
    guild = 720001
    assert await service.resolve(guild, "welcome") is None      # nothing configured
    await service.set_channel(guild, "welcome", 42)             # enables in one write
    assert await service.resolve(guild, "welcome") == (42, service.DEFAULT_WELCOME)


async def test_custom_message_then_disable():
    await _schema()
    guild = 720002
    await service.set_channel(guild, "goodbye", 7)
    await service.set_message(guild, "goodbye", "bye {name}")
    assert await service.resolve(guild, "goodbye") == (7, "bye {name}")
    await service.set_enabled(guild, "goodbye", False)
    assert await service.resolve(guild, "goodbye") is None


async def test_summary_reports_both_kinds_independently():
    await _schema()
    guild = 720003
    await service.set_channel(guild, "welcome", 1)
    s = await service.get_summary(guild)
    assert s["welcome"]["enabled"] is True and s["welcome"]["channel_id"] == 1
    assert s["goodbye"]["enabled"] is False


# ── placeholder rendering ────────────────────────────────────────────────────

def test_render_fills_placeholders():
    member = SimpleNamespace(
        mention="<@5>", display_name="Nick",
        guild=SimpleNamespace(name="Soju", member_count=10),
    )
    out = render("{user} {name} joined {server} as #{count}", member)
    assert out == "<@5> Nick joined Soju as #10"
