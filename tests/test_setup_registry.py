"""Tests for the ,setup panel registry: registration, listing, and matching.

Pure and synchronous — no Discord. Each test runs against a cleared registry (the
fixture snapshots and restores the real one) so it never depends on whichever
modules happen to have registered during import.
"""

from __future__ import annotations

import pytest

from src.core import setup_registry
from src.core.setup_registry import SetupEntry


def _entry(key: str, label: str | None = None) -> SetupEntry:
    return SetupEntry(
        key=key,
        label=label or key.capitalize(),
        emoji="⚙️",
        description=f"Configure {key}.",
        factory=lambda author_id, guild_id: None,
    )


@pytest.fixture(autouse=True)
def _clean_registry():
    saved = dict(setup_registry._REGISTRY)
    setup_registry._REGISTRY.clear()
    try:
        yield
    finally:
        setup_registry._REGISTRY.clear()
        setup_registry._REGISTRY.update(saved)


def test_register_then_get_and_list():
    e = _entry("levels", "Leveling")
    setup_registry.register_setup(e)
    assert setup_registry.get_entry("levels") is e
    assert setup_registry.all_entries() == [e]


def test_register_same_key_replaces():
    setup_registry.register_setup(_entry("levels", "Leveling"))
    setup_registry.register_setup(_entry("levels", "Leveling 2"))
    assert len(setup_registry.all_entries()) == 1
    assert setup_registry.get_entry("levels").label == "Leveling 2"


def test_all_entries_sorted_by_label():
    setup_registry.register_setup(_entry("prefix", "Prefix"))
    setup_registry.register_setup(_entry("levels", "Leveling"))
    setup_registry.register_setup(_entry("logging", "Logging"))
    assert [e.label for e in setup_registry.all_entries()] == ["Leveling", "Logging", "Prefix"]


def test_match_exact_prefix_and_substring():
    setup_registry.register_setup(_entry("levels", "Leveling"))
    setup_registry.register_setup(_entry("prefix", "Prefix"))
    assert setup_registry.match_entry("levels").key == "levels"    # exact key
    assert setup_registry.match_entry("Leveling").key == "levels"  # exact label (case-insensitive)
    assert setup_registry.match_entry("lev").key == "levels"       # unique prefix
    assert setup_registry.match_entry("refi").key == "prefix"      # unique substring


def test_match_returns_none_on_miss_or_ambiguous():
    setup_registry.register_setup(_entry("levels", "Leveling"))
    setup_registry.register_setup(_entry("leaderboard", "Leaderboard"))
    assert setup_registry.match_entry("nope") is None  # no match
    assert setup_registry.match_entry("le") is None    # ambiguous: both contain "le"
    assert setup_registry.match_entry("") is None      # empty query


def test_unregister_removes_and_noops_when_absent():
    setup_registry.register_setup(_entry("levels"))
    setup_registry.unregister_setup("levels")
    assert setup_registry.get_entry("levels") is None
    setup_registry.unregister_setup("levels")  # absent — must not raise
