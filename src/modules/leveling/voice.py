"""Pure, testable bookkeeping for voice-time accrual.

The cog feeds observations — *is this member eligible right now, and in which
channel* — on every voice-state change and once per flush tick. The tracker keeps
each member's open eligible interval, accumulates seconds across mute/unmute (and
undeafen) gaps within one presence, and hands back whole minutes to write —
batched — per ``(guild, user, channel)`` so per-channel XP multipliers still
apply. Sub-minute remainder is dropped when a member leaves the channel entirely.

No Discord, no DB, no clock: ``now`` is passed in, so this is fully unit-testable.
"""

from __future__ import annotations

Key = tuple[int, int]  # (guild_id, user_id)
ChannelKey = tuple[int, int, int]  # (guild_id, user_id, channel_id)


class VoiceTracker:
    def __init__(self) -> None:
        self._open: dict[Key, tuple[int, float]] = {}   # key -> (channel_id, started_at)
        self._carry: dict[ChannelKey, float] = {}       # leftover eligible seconds (< 60)
        self._pending: dict[ChannelKey, int] = {}       # whole minutes awaiting a DB flush

    def observe(self, key: Key, channel_id: int | None, eligible: bool, now: float) -> None:
        """Record a member's current state: close any open interval (banking its
        seconds), then re-open one if they're eligible. Called on every transition
        for the member and for everyone whose 'alone' status their move flipped."""
        self._close(key, now)
        if eligible and channel_id is not None:
            self._open[key] = (channel_id, now)

    def leave(self, key: Key, now: float) -> None:
        """The member left voice entirely: bank whole minutes, drop the remainder."""
        self._close(key, now)
        for ck in [ck for ck in self._carry if (ck[0], ck[1]) == key]:
            del self._carry[ck]

    def checkpoint(self, now: float) -> None:
        """Bank elapsed time on still-open intervals so long, event-less sessions
        keep accruing. Re-opens each interval at ``now``."""
        for key, (channel_id, started) in list(self._open.items()):
            self._bank(key, channel_id, now - started)
            self._open[key] = (channel_id, now)

    def drain(self) -> list[tuple[int, int, int, int]]:
        """Take the minutes ready to write: ``[(guild, user, channel, minutes)]``."""
        out = [(g, u, c, m) for (g, u, c), m in self._pending.items() if m > 0]
        self._pending.clear()
        return out

    def restore(self, batch: list[tuple[int, int, int, int]]) -> None:
        """Put a drained batch back (e.g. the DB write failed) so it isn't lost."""
        for g, u, c, m in batch:
            self._pending[(g, u, c)] = self._pending.get((g, u, c), 0) + m

    def _close(self, key: Key, now: float) -> None:
        entry = self._open.pop(key, None)
        if entry is not None:
            channel_id, started = entry
            self._bank(key, channel_id, now - started)

    def _bank(self, key: Key, channel_id: int, seconds: float) -> None:
        if seconds <= 0:
            return
        ck = (key[0], key[1], channel_id)
        total = self._carry.get(ck, 0.0) + seconds
        minutes = int(total // 60)
        if minutes:
            self._pending[ck] = self._pending.get(ck, 0) + minutes
            total -= minutes * 60
        self._carry[ck] = total
