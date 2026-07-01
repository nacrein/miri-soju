"""Economy tuning. Every number lives here; nothing is hardcoded in commands.

Scale: a million bits is a multi-week goal. Daily faucet in the hundreds.
"""

from __future__ import annotations

from datetime import timedelta

from src.core.emojis import Emojis

# ── daily ───────────────────────────────────────────────────────────────────
DAILY_COOLDOWN = timedelta(hours=20)
DAILY_RESET_GRACE = timedelta(hours=28)  # miss beyond this and the streak resets
DAILY_STREAK_REWARDS = [250, 400, 600, 850, 1100, 1300, 1500]  # index 0 = day 1
DAILY_STREAK_MAX = len(DAILY_STREAK_REWARDS)

# ── work ────────────────────────────────────────────────────────────────────
WORK_COOLDOWN = timedelta(hours=1)
WORK_MIN = 150
WORK_MAX = 400

# ── pray ────────────────────────────────────────────────────────────────────
PRAY_COOLDOWN = timedelta(hours=2)
PRAY_MIN = 50
PRAY_MAX = 1200
PRAY_BLESSING_CHANCE = 0.10   # chance of the big payout
PRAY_BLESSING_MIN = 800
PRAY_BLESSING_MAX = 1200

# Short per-user command cooldown for daily/work/pray (spam guard). Their real
# (hours-long) cooldowns are enforced in the DB; this just stops rapid re-invocation.
FAUCET_COOLDOWN_SECONDS = 5

# ── give ────────────────────────────────────────────────────────────────────
GIVE_MIN = 1

# ── staff ───────────────────────────────────────────────────────────────────
# Ceiling on a single staff mint (,staff give). Guards a fat-finger (e.g. a
# pasted 17-19 digit user ID) from minting an unbounded, irreversible amount.
STAFF_GRANT_MAX = 1_000_000_000

# ── vault ───────────────────────────────────────────────────────────────────
# (capacity, total cost to have unlocked up to this capacity)
VAULT_TIERS = [
    (50_000, 0),          # everyone starts with 50k free
    (100_000, 25_000),
    (250_000, 100_000),
    (500_000, 300_000),
    (1_000_000, 750_000),
    (2_500_000, 2_000_000),
    (5_000_000, 5_000_000),
]
VAULT_BASE_CAPACITY = VAULT_TIERS[0][0]

# ── generator ───────────────────────────────────────────────────────────────
# tier -> (bits per hour, cost to reach this tier from the previous)
GENERATOR_TIERS = {
    0: (0, 0),            # not owned
    1: (100, 10_000),
    2: (250, 30_000),
    3: (600, 80_000),
    4: (1_400, 200_000),
    5: (3_000, 500_000),
}
GENERATOR_MAX_HOURS = 24   # income caps after this long uncollected (encourages return)

# ── income multiplier seam ──────────────────────────────────────────────────
# Today every player's multiplier is 1.0; later this reads active bonuses.
BASE_INCOME_MULTIPLIER = 1.0



# ── beg ─────────────────────────────────────────────────────────────────────
BEG_COOLDOWN_SECONDS = 45   # enforced by the command decorator (resets on restart)
BEG_MIN = 1
BEG_MAX = 50
BEG_FAIL_CHANCE = 0.25      # chance the beg yields nothing


# ── steal ───────────────────────────────────────────────────────────────────
STEAL_COOLDOWN = timedelta(hours=4)
STEAL_SUCCESS_CHANCE = 0.40
STEAL_MAX_PCT = 0.20            # take at most this fraction of target's wallet
STEAL_FINE_PCT = 0.10          # on failure, pay this fraction of YOUR wallet as a fine
STEAL_TARGET_FLOOR = 5_000     # targets below this wallet can't be stolen from (protect the poor)
STEAL_MIN_FINE = 100           # minimum fine so failure always stings a little

# ── gambling ────────────────────────────────────────────────────────────────
# A fair coinflip pays 2.0x on win (even money). We pay slightly less so the
# house has an edge. payout_multiplier_on_win = 2.0 * (1 - HOUSE_EDGE).
HOUSE_EDGE = 0.02

GAMBLE_MIN_BET = 10  # no upper cap; a wager is limited only by the player's wallet

# slots: symbol -> (weight, three-of-a-kind multiplier)
# Symbol -> (weight, three-of-a-kind multiplier). Tuned so the machine's
# expected value is ~0.81 per bit (a real ~19% house edge, verified by sim).
SLOTS_SYMBOLS = {
    Emojis.CHERRY: (40, 3),
    Emojis.LEMON: (30, 7),
    Emojis.BELL: (18, 15),
    Emojis.GEM: (10, 50),
    Emojis.SLOTS: (2, 300),   # jackpot
}
# Two matching returns half the stake (a softened loss, not a win), which keeps
# frequent near-misses from leaking the house edge.
SLOTS_TWO_MATCH_MULT = 0.5

# roulette payouts (European-style single-zero feel)
ROULETTE_RED_BLACK_MULT = 2    # ~even money
ROULETTE_DOZEN_MULT = 3
ROULETTE_NUMBER_MULT = 35
ROULETTE_SLOTS = 37            # 0-36; 0 is the house number


# ── ladder ──────────────────────────────────────────────────────────────────
# Each rung: (multiplier_if_you_stop_here, chance_of_busting_to_climb_past_it).
# EV is kept < 1 at every climb decision so the house edge holds.
LADDER_RUNGS = [
    (1.3, 0.25),
    (1.7, 0.30),
    (2.3, 0.35),
    (3.2, 0.40),
    (4.5, 0.45),
    (7.0, 0.55),
]

# ── crash ───────────────────────────────────────────────────────────────────
CRASH_TICK_GROWTH = 0.20       # multiplier gains this per tick
CRASH_BASE_CRASH_CHANCE = 0.18 # chance to crash each tick (house edge lives here)
CRASH_START_MULT = 1.0

# ── blackjack ───────────────────────────────────────────────────────────────
BLACKJACK_PAYOUT = 2.0         # win returns 2x stake (even money on the wager)
BLACKJACK_NATURAL_PAYOUT = 2.5 # a natural 21 pays 3:2

# ── dice ────────────────────────────────────────────────────────────────────
DICE_SIDES = 100        # rolls 0..99
DICE_MIN_TARGET = 2     # roll-under floor (~2% win chance, ~49x)
DICE_MAX_TARGET = 98    # roll-under ceiling (~98% win chance, ~1x)

# ── limbo ───────────────────────────────────────────────────────────────────
LIMBO_MIN_TARGET = 1.01
LIMBO_MAX_TARGET = 1000.0

# ── plinko ──────────────────────────────────────────────────────────────────
PLINKO_ROWS = 8
# Bucket multipliers (index 0..PLINKO_ROWS), weighted by C(8,k)/256 so the
# probability-weighted EV is ~0.979 (a ~2% edge, verified by the sim below).
PLINKO_MULTIPLIERS = [5.0, 2.0, 1.1, 1.0, 0.5, 1.0, 1.1, 2.0, 5.0]
