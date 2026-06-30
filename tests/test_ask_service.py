"""Behavioral tests for the ,ask service seam.

These cover the security/cost guards added to ``src.modules.ask.service``:
 - owner trust is sourced from ``settings.owner_id`` and resolved in code, never
   embedding the raw owner snowflake in the prompt (findings 1, 2, 4),
 - the user prompt is clamped before it is billed as input tokens (finding 3),
 - a process-wide requests-per-minute ceiling caps paid API spend (finding 3).

No network or real API key is touched: the Anthropic client is replaced with a
fake that records the ``system``/``prompt`` it was handed and returns canned text.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.core.errors import BotError
from src.modules.ask import service


class _FakeMessages:
    def __init__(self, recorder: dict) -> None:
        self._rec = recorder

    async def create(self, *, model, max_tokens, system, messages):
        self._rec["system"] = system
        self._rec["messages"] = messages
        return SimpleNamespace(
            stop_reason="end_turn",
            content=[SimpleNamespace(type="text", text="ok")],
        )


class _FakeClient:
    def __init__(self, recorder: dict) -> None:
        self.messages = _FakeMessages(recorder)


@pytest.fixture
def captured(monkeypatch):
    """Wire a fake client + a baked system prompt; return the call recorder."""
    rec: dict = {}
    monkeypatch.setattr(service, "_get_client", lambda: _FakeClient(rec))
    # Skip the live command-list bake; give a stable base prompt.
    monkeypatch.setattr(service, "_system", "BASE")
    # Reset the rolling rate-limit window between tests.
    monkeypatch.setattr(service, "_recent_calls", [])
    return rec


def _set_owner(monkeypatch, owner_id: int | None) -> None:
    monkeypatch.setattr(
        service, "get_settings", lambda: SimpleNamespace(owner_id=owner_id)
    )


# ── owner trust comes from settings, raw ID never embedded ──────────────────

async def test_owner_match_uses_owner_clause(captured, monkeypatch):
    _set_owner(monkeypatch, 4242)
    await service.ask(None, 4242, "hi")
    system = captured["system"]
    assert "is your owner" in system
    assert "is not your owner" not in system


async def test_non_owner_gets_not_owner_clause(captured, monkeypatch):
    _set_owner(monkeypatch, 4242)
    await service.ask(None, 9999, "hi")
    assert "is not your owner" in captured["system"]


async def test_no_owner_configured_is_treated_as_not_owner(captured, monkeypatch):
    _set_owner(monkeypatch, None)
    await service.ask(None, 4242, "hi")
    assert "is not your owner" in captured["system"]


async def test_raw_owner_id_and_author_id_never_embedded(captured, monkeypatch):
    # The old hardcoded literal and the asker's snowflake must not leak into the prompt.
    _set_owner(monkeypatch, 4242)
    await service.ask(None, 7777, "hi")
    system = captured["system"]
    assert "1402932059181285438" not in system
    assert "4242" not in system
    assert "7777" not in system


# ── prompt length clamp (input-token cost guard) ────────────────────────────

async def test_long_prompt_is_clamped(captured, monkeypatch):
    _set_owner(monkeypatch, 1)
    huge = "x" * 10_000
    await service.ask(None, 1, huge)
    sent = captured["messages"][0]["content"]
    assert len(sent) == service._MAX_PROMPT_CHARS


async def test_short_prompt_is_untouched(captured, monkeypatch):
    _set_owner(monkeypatch, 1)
    await service.ask(None, 1, "what's up")
    assert captured["messages"][0]["content"] == "what's up"


# ── global requests-per-minute ceiling ──────────────────────────────────────

async def test_global_budget_blocks_after_ceiling(captured, monkeypatch):
    _set_owner(monkeypatch, 1)
    for _ in range(service._GLOBAL_RPM):
        await service.ask(None, 1, "hi")
    with pytest.raises(BotError):
        await service.ask(None, 1, "one too many")


async def test_global_budget_evicts_stale_calls(monkeypatch):
    # Pre-load the window with calls older than 60s; they should be evicted, so a
    # fresh call is allowed rather than counted against the ceiling.
    monkeypatch.setattr(service, "_recent_calls", [0.0] * service._GLOBAL_RPM)
    monkeypatch.setattr(service.time, "monotonic", lambda: 10_000.0)
    service._check_global_budget()  # must not raise
    assert service._recent_calls == [10_000.0]
