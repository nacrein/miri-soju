"""Pure game logic for the interactive games. No Discord, no DB — testable."""

from __future__ import annotations

import random
from dataclasses import dataclass, field

# ── blackjack ───────────────────────────────────────────────────────────────

_RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
_SUITS = ["♠", "♥", "♦", "♣"]


def _card_value(rank: str) -> int:
    if rank in ("J", "Q", "K"):
        return 10
    if rank == "A":
        return 11
    return int(rank)


def hand_total(cards: list[tuple[str, str]]) -> int:
    """Best blackjack total, treating aces as 11 then 1 as needed."""
    total = sum(_card_value(r) for r, _ in cards)
    aces = sum(1 for r, _ in cards if r == "A")
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total


def is_blackjack(cards: list[tuple[str, str]]) -> bool:
    return len(cards) == 2 and hand_total(cards) == 21


@dataclass
class BlackjackGame:
    """Server-side blackjack state. The deck and hands never leave the server."""

    deck: list[tuple[str, str]] = field(default_factory=list)
    player: list[tuple[str, str]] = field(default_factory=list)
    dealer: list[tuple[str, str]] = field(default_factory=list)
    finished: bool = False

    def __post_init__(self) -> None:
        if not self.deck:
            self.deck = [(r, s) for s in _SUITS for r in _RANKS]
            random.shuffle(self.deck)
            self.player = [self.deck.pop(), self.deck.pop()]
            self.dealer = [self.deck.pop(), self.deck.pop()]

    def hit(self) -> None:
        self.player.append(self.deck.pop())

    def dealer_play(self) -> None:
        while hand_total(self.dealer) < 17:
            self.dealer.append(self.deck.pop())

    def result(self) -> str:
        """One of: 'natural', 'win', 'push', 'lose', 'bust'."""
        pt = hand_total(self.player)
        if pt > 21:
            return "bust"
        if is_blackjack(self.player) and not is_blackjack(self.dealer):
            return "natural"
        dt = hand_total(self.dealer)
        if dt > 21 or pt > dt:
            return "win"
        if pt == dt:
            return "push"
        return "lose"


# ── ladder ──────────────────────────────────────────────────────────────────

def ladder_climb_busts(rung_index: int, rungs: list[tuple[float, float]]) -> bool:
    """True if climbing PAST the given rung busts (loses everything)."""
    _mult, bust_chance = rungs[rung_index]
    return random.random() < bust_chance


# ── crash ───────────────────────────────────────────────────────────────────

def crash_tick(crash_chance: float) -> bool:
    """True if the multiplier crashes this tick."""
    return random.random() < crash_chance


# ── hi-lo ────────────────────────────────────────────────────────────────────

_HILO_FACES = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]


def hilo_draw() -> int:
    """A card rank as a value 1 (low, '2') .. 13 (high, 'A'). Drawn with replacement."""
    return random.randint(1, 13)


def hilo_face(value: int) -> str:
    return _HILO_FACES[value - 1]


def hilo_multipliers(current: int, house_edge: float) -> tuple[float, float]:
    """(higher_or_same, lower_or_same) total-return multipliers for the current card.

    P(next >= current) = (14 - current)/13 and P(next <= current) = current/13; the two
    overlap on a tie so an extreme card always has a winning side. Each pays inverse
    probability shaved by the edge, so EV per pick is 1 - house_edge.
    """
    p_higher = (14 - current) / 13
    p_lower = current / 13
    return (1 - house_edge) / p_higher, (1 - house_edge) / p_lower
