"""Registry of interactive ``,setup`` panels.

Each feature module registers a :class:`SetupEntry` for itself when its cog loads;
the ``setup`` cog reads only this registry to build the module picker and to
dispatch ``,setup <module>``. Core owns the registry data structure and imports no
feature module — features call ``register_setup`` (modules → core), so the
dependency only ever points one way (see the "core has no feature imports" rule).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import discord

# (author_id, guild_id) -> a freshly built panel view for that invoker and guild.
WizardFactory = Callable[[int, int], "discord.ui.View"]


@dataclass(frozen=True)
class SetupEntry:
    """One module's setup panel, as the picker and dispatcher see it."""

    key: str          # "levels" — the ,setup argument and the select value
    label: str        # "Leveling" — shown on the picker option
    emoji: str        # an Emojis.* string for the option
    description: str  # one line (≤100 chars) shown under the option
    factory: WizardFactory


_REGISTRY: dict[str, SetupEntry] = {}


def register_setup(entry: SetupEntry) -> None:
    """Register (or replace) a module's panel. Idempotent, so cog reloads are safe."""
    _REGISTRY[entry.key] = entry


def unregister_setup(key: str) -> None:
    """Drop a module's panel; a no-op if it isn't registered (cog unload)."""
    _REGISTRY.pop(key, None)


def get_entry(key: str) -> SetupEntry | None:
    return _REGISTRY.get(key)


def all_entries() -> list[SetupEntry]:
    """Every registered panel, sorted by label for a stable picker order."""
    return sorted(_REGISTRY.values(), key=lambda e: e.label.lower())


def match_entry(query: str) -> SetupEntry | None:
    """Resolve a ``,setup <query>`` argument to a single panel.

    An exact key or label match wins; otherwise a *unique* prefix/substring match.
    Returns None on no match or an ambiguous one, so the caller can list the keys.
    """
    q = query.strip().lower()
    if not q:
        return None
    for entry in _REGISTRY.values():
        if entry.key.lower() == q or entry.label.lower() == q:
            return entry
    hits = [
        entry
        for entry in _REGISTRY.values()
        if q in entry.key.lower() or q in entry.label.lower()
    ]
    return hits[0] if len(hits) == 1 else None
