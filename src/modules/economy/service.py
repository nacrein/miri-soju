"""Economy logic: validated, atomic, race-safe money operations.

Security model:
  * validate_amount() rejects non-positive / non-int bets at the boundary.
  * Every mutation runs in one transaction over a row-locked player, so
    concurrent commands queue instead of racing a stale balance.
  * The wallet/vault check constraints are the final backstop.
  * All income flows through apply_multiplier() — the seam where future
    membership / card bonuses attach without touching any faucet.
"""

from __future__ import annotations

import random
import uuid
from datetime import datetime, timezone

from src.core.errors import BotError
from src.database.session import get_session
from src.modules.economy import config
from src.database.models.transaction import Transaction
from src.modules.economy.repository import EconomyRepository


class EconomyError(BotError):
    """User-facing economy failure (insufficient funds, on cooldown, etc.)."""


# ── security: amount validation ─────────────────────────────────────────────

def validate_amount(amount: int) -> int:
    """Reject anything that isn't a positive integer. First wall vs injection."""
    if not isinstance(amount, int) or isinstance(amount, bool):
        raise EconomyError("Amount must be a whole number.")
    if amount <= 0:
        raise EconomyError("Amount must be positive.")
    return amount


# ── income multiplier seam ──────────────────────────────────────────────────

def apply_multiplier(player, base_amount: int) -> int:
    """Apply the player's income multiplier. Today always 1.0."""
    return int(base_amount * config.BASE_INCOME_MULTIPLIER)


def _record(session, player, kind: str, amount: int,
            counterparty_id: int | None = None, note: str | None = None,
            game_session_id: str | None = None) -> None:
    """Append a ledger row using the ACTIVE session, so it commits atomically
    with the balance change it describes. amount is signed (+gain / -loss).

    game_session_id is set only for interactive-game rows so a stake and its
    resolution can be paired exactly; it stays None for every other kind."""
    session.add(Transaction(
        discord_id=player.discord_id,
        kind=kind,
        amount=amount,
        balance_after=player.wallet,
        counterparty_id=counterparty_id,
        note=note,
        game_session_id=game_session_id,
    ))


# ── cooldown helper ─────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    """Normalize a stored datetime to tz-aware UTC. SQLite returns naive values;
    Postgres returns aware ones. This makes comparisons backend-independent."""
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _cooldown_remaining(last: datetime | None, cooldown) -> int:
    """Seconds left on a cooldown, or 0 if ready. Non-raising (for display)."""
    last = _aware(last)
    if last is None:
        return 0
    elapsed = _now() - last
    if elapsed >= cooldown:
        return 0
    return int((cooldown - elapsed).total_seconds())


def _fmt_remaining(secs: int) -> str:
    if secs <= 0:
        return "ready"
    h, m = secs // 3600, (secs % 3600) // 60
    if h:
        return f"{h}h {m}m"
    if m:
        return f"{m}m"
    return f"{secs}s"


def _check_cooldown(last: datetime | None, cooldown, label: str) -> None:
    last = _aware(last)
    if last is None:
        return
    elapsed = _now() - last
    if elapsed < cooldown:
        remaining = cooldown - elapsed
        secs = int(remaining.total_seconds())
        h, m = secs // 3600, (secs % 3600) // 60
        when = f"{h}h {m}m" if h else f"{m}m"
        raise EconomyError(f"`{label}` is on cooldown. Try again in {when}.")


# ── read-only balance ───────────────────────────────────────────────────────

async def get_balance(discord_id: int) -> tuple[int, int, int]:
    """Return (wallet, vault, vault_capacity)."""
    async with get_session() as session:
        repo = EconomyRepository(session)
        player = await repo.get_or_create(discord_id)
        return player.wallet, player.vault, player.vault_capacity


# ── faucets ─────────────────────────────────────────────────────────────────

async def claim_daily(discord_id: int) -> tuple[int, int]:
    """Claim daily. Returns (amount, streak_day)."""
    async with get_session() as session:
        repo = EconomyRepository(session)
        player = await repo.get_or_create_for_update(discord_id)
        _check_cooldown(player.last_daily_at, config.DAILY_COOLDOWN, "daily")

        # Streak: continue if within grace, else reset.
        if player.last_daily_at is not None and (_now() - _aware(player.last_daily_at)) > config.DAILY_RESET_GRACE:
            player.daily_streak = 0
        player.daily_streak = min(player.daily_streak + 1, config.DAILY_STREAK_MAX)

        base = config.DAILY_STREAK_REWARDS[player.daily_streak - 1]
        amount = apply_multiplier(player, base)
        player.wallet += amount
        player.last_daily_at = _now()
        _record(session, player, "daily", amount)
        return amount, player.daily_streak


async def work(discord_id: int) -> int:
    async with get_session() as session:
        repo = EconomyRepository(session)
        player = await repo.get_or_create_for_update(discord_id)
        _check_cooldown(player.last_work_at, config.WORK_COOLDOWN, "work")
        amount = apply_multiplier(player, random.randint(config.WORK_MIN, config.WORK_MAX))
        player.wallet += amount
        player.last_work_at = _now()
        _record(session, player, "work", amount)
        return amount


async def pray(discord_id: int) -> tuple[int, bool]:
    """Returns (amount, was_blessing)."""
    async with get_session() as session:
        repo = EconomyRepository(session)
        player = await repo.get_or_create_for_update(discord_id)
        _check_cooldown(player.last_pray_at, config.PRAY_COOLDOWN, "pray")
        if random.random() < config.PRAY_BLESSING_CHANCE:
            base = random.randint(config.PRAY_BLESSING_MIN, config.PRAY_BLESSING_MAX)
            blessing = True
        else:
            base = random.randint(config.PRAY_MIN, config.PRAY_MAX)
            blessing = False
        amount = apply_multiplier(player, base)
        player.wallet += amount
        player.last_pray_at = _now()
        _record(session, player, "pray", amount, note="blessing" if blessing else None)
        return amount, blessing


# ── transfer ────────────────────────────────────────────────────────────────

async def give(sender_id: int, receiver_id: int, amount: int) -> None:
    """Atomic transfer from sender's wallet to receiver's wallet."""
    validate_amount(amount)
    if sender_id == receiver_id:
        raise EconomyError("You can't give to yourself.")
    async with get_session() as session:
        repo = EconomyRepository(session)
        # Ensure both rows exist, then lock both in a stable order (by id) to
        # avoid deadlocks. Map the locked rows back to sender/receiver by id.
        await repo.get_or_create(sender_id)
        await repo.get_or_create(receiver_id)
        first, second = sorted((sender_id, receiver_id))
        row_first = await repo.get_for_update(first)
        row_second = await repo.get_for_update(second)
        rows = {first: row_first, second: row_second}
        sender, receiver = rows[sender_id], rows[receiver_id]
        if sender.wallet < amount:
            raise EconomyError("You don't have enough bits in your wallet.")
        sender.wallet -= amount
        receiver.wallet += amount
        _record(session, sender, "give_sent", -amount, counterparty_id=receiver_id)
        _record(session, receiver, "give_received", amount, counterparty_id=sender_id)


# ── vault ───────────────────────────────────────────────────────────────────

async def deposit(discord_id: int, amount: int) -> int:
    """Move wallet -> vault, bounded by capacity. Returns deposited amount."""
    validate_amount(amount)
    async with get_session() as session:
        repo = EconomyRepository(session)
        player = await repo.get_or_create_for_update(discord_id)
        if player.wallet < amount:
            raise EconomyError("You don't have that many bits in your wallet.")
        space = player.vault_capacity - player.vault
        if space <= 0:
            raise EconomyError("Your vault is full. Upgrade it for more space.")
        moved = min(amount, space)
        player.wallet -= moved
        player.vault += moved
        _record(session, player, "vault_deposit", -moved)
        return moved


async def withdraw(discord_id: int, amount: int) -> int:
    """Move vault -> wallet. Returns withdrawn amount."""
    validate_amount(amount)
    async with get_session() as session:
        repo = EconomyRepository(session)
        player = await repo.get_or_create_for_update(discord_id)
        if player.vault < amount:
            raise EconomyError("You don't have that many bits in your vault.")
        player.vault -= amount
        player.wallet += amount
        _record(session, player, "vault_withdraw", amount)
        return amount


# ── vault expansion + generators ────────────────────────────────────────────


def _current_vault_tier(capacity: int) -> int:
    """Index of the highest tier whose capacity the player has unlocked."""
    tier = 0
    for i, (cap, _cost) in enumerate(config.VAULT_TIERS):
        if capacity >= cap:
            tier = i
    return tier


def vault_upgrade_info(capacity: int) -> tuple[int, int] | None:
    """Return (next_capacity, cost_to_upgrade) or None if maxed."""
    current = _current_vault_tier(capacity)
    if current >= len(config.VAULT_TIERS) - 1:
        return None
    next_cap, next_total = config.VAULT_TIERS[current + 1]
    _cap, current_total = config.VAULT_TIERS[current]
    # Pay the difference between cumulative costs (you already "paid" up to here).
    return next_cap, next_total - current_total


async def upgrade_vault(discord_id: int) -> tuple[int, int]:
    """Buy the next vault capacity tier. Returns (new_capacity, cost_paid)."""
    async with get_session() as session:
        repo = EconomyRepository(session)
        player = await repo.get_or_create_for_update(discord_id)
        info = vault_upgrade_info(player.vault_capacity)
        if info is None:
            raise EconomyError("Your vault is already at maximum capacity.")
        new_cap, cost = info
        if player.wallet < cost:
            raise EconomyError(
                f"You need {cost:,} bits in your wallet to upgrade (you have {player.wallet:,})."
            )
        player.wallet -= cost
        player.vault_capacity = new_cap
        _record(session, player, "vault_upgrade", -cost, note=f"capacity {new_cap}")
        return new_cap, cost


# ── generators ──────────────────────────────────────────────────────────────

def _generator_accrued(tier: int, claimed_at: datetime | None) -> int:
    """Bits accumulated since last claim, capped at GENERATOR_MAX_HOURS."""
    if tier <= 0 or claimed_at is None:
        return 0
    rate, _cost = config.GENERATOR_TIERS[tier]
    hours = (_now() - _aware(claimed_at)).total_seconds() / 3600
    hours = min(hours, config.GENERATOR_MAX_HOURS)
    return int(rate * hours)


def generator_status(player) -> tuple[int, int, int]:
    """Return (tier, rate_per_hour, pending_bits) for display."""
    rate = config.GENERATOR_TIERS.get(player.generator_tier, (0, 0))[0]
    pending = _generator_accrued(player.generator_tier, player.generator_claimed_at)
    return player.generator_tier, rate, pending


async def get_generator(discord_id: int) -> tuple[int, int, int]:
    async with get_session() as session:
        repo = EconomyRepository(session)
        player = await repo.get_or_create(discord_id)
        return generator_status(player)


async def claim_generator(discord_id: int) -> int:
    """Collect accrued generator bits into the wallet. Returns amount."""
    async with get_session() as session:
        repo = EconomyRepository(session)
        player = await repo.get_or_create_for_update(discord_id)
        if player.generator_tier <= 0:
            raise EconomyError("You don't own a generator yet. Use the upgrade command to buy one.")
        base = _generator_accrued(player.generator_tier, player.generator_claimed_at)
        if base <= 0:
            raise EconomyError("Nothing to collect yet. Check back later.")
        amount = apply_multiplier(player, base)
        player.wallet += amount
        player.generator_claimed_at = _now()
        _record(session, player, "generator_claim", amount)
        return amount


def generator_upgrade_info(tier: int) -> tuple[int, int, int] | None:
    """Return (next_tier, next_rate, cost) or None if maxed."""
    next_tier = tier + 1
    if next_tier not in config.GENERATOR_TIERS:
        return None
    rate, cost = config.GENERATOR_TIERS[next_tier]
    return next_tier, rate, cost


async def upgrade_generator(discord_id: int) -> tuple[int, int, int]:
    """Buy the next generator tier. Auto-claims pending bits first so none are lost.

    Returns (new_tier, new_rate, cost_paid).
    """
    async with get_session() as session:
        repo = EconomyRepository(session)
        player = await repo.get_or_create_for_update(discord_id)
        info = generator_upgrade_info(player.generator_tier)
        if info is None:
            raise EconomyError("Your generator is already at maximum tier.")
        new_tier, new_rate, cost = info
        if player.wallet < cost:
            raise EconomyError(
                f"You need {cost:,} bits in your wallet to upgrade (you have {player.wallet:,})."
            )
        # Collect anything pending before changing the rate, so it's not lost/miscounted.
        pending = _generator_accrued(player.generator_tier, player.generator_claimed_at)
        if pending > 0:
            credited = apply_multiplier(player, pending)
            player.wallet += credited
            _record(session, player, "generator_claim", credited, note="auto on upgrade")
        player.wallet -= cost
        player.generator_tier = new_tier
        player.generator_claimed_at = _now()
        _record(session, player, "generator_upgrade", -cost, note=f"tier {new_tier}")
        return new_tier, new_rate, cost


# ── gambling ────────────────────────────────────────────────────────────────


def validate_bet(amount: int) -> int:
    """Validate a wager: positive int within the configured bet bounds."""
    validate_amount(amount)
    if amount < config.GAMBLE_MIN_BET:
        raise EconomyError(f"Minimum bet is {config.GAMBLE_MIN_BET:,} bits.")
    if amount > config.GAMBLE_MAX_BET:
        raise EconomyError(f"Maximum bet is {config.GAMBLE_MAX_BET:,} bits.")
    return amount


async def settle_bet(discord_id: int, amount: int, multiplier: float) -> tuple[int, int]:
    """The atomic heart of every game.

    Deducts the stake and applies the result inside one locked transaction, so a
    bet can never be raced, double-paid, or left half-applied. `multiplier` is
    the game outcome: 0 = total loss, 2.0 = doubled (minus house edge applied by
    the caller's game logic), etc.

    Returns (net_change, new_wallet). net_change is winnings minus stake.
    """
    validate_bet(amount)
    async with get_session() as session:
        repo = EconomyRepository(session)
        player = await repo.get_or_create_for_update(discord_id)
        if player.wallet < amount:
            raise EconomyError("You don't have that many bits in your wallet.")
        payout = int(amount * multiplier)
        net = payout - amount
        player.wallet += net  # deduct stake and add payout in one move
        _record(session, player, "gamble_win" if net >= 0 else "gamble_loss", net)
        return net, player.wallet


# ── steal ───────────────────────────────────────────────────────────────────

async def steal(thief_id: int, victim_id: int) -> tuple[bool, int]:
    """Attempt to steal from a victim's WALLET (vault is untouchable).

    Returns (success, delta). On success delta is bits gained; on failure delta
    is the fine paid (negative). Fully rule-bounded: success chance, caps, a
    floor protecting poor targets, and a fine on failure.
    """
    if thief_id == victim_id:
        raise EconomyError("You can't steal from yourself.")
    async with get_session() as session:
        repo = EconomyRepository(session)
        # Ensure both rows exist, then lock both in a stable order to avoid
        # deadlocks. Map the locked rows back to thief/victim by id.
        await repo.get_or_create(thief_id)
        await repo.get_or_create(victim_id)
        first, second = sorted((thief_id, victim_id))
        row_first = await repo.get_for_update(first)
        row_second = await repo.get_for_update(second)
        rows = {first: row_first, second: row_second}
        thief, victim = rows[thief_id], rows[victim_id]

        # All validation that can raise happens BEFORE the cooldown is stamped,
        # so a rejected attempt never consumes the thief's cooldown.
        _check_cooldown(thief.last_steal_at, config.STEAL_COOLDOWN, "steal")
        if victim.wallet < config.STEAL_TARGET_FLOOR:
            raise EconomyError("That player is too poor to be worth stealing from.")

        thief.last_steal_at = _now()

        import random as _r
        if _r.random() < config.STEAL_SUCCESS_CHANCE:
            take = int(victim.wallet * config.STEAL_MAX_PCT)
            take = max(take, 1)
            victim.wallet -= take
            thief.wallet += take
            _record(session, thief, "steal_gain", take, counterparty_id=victim_id)
            _record(session, victim, "steal_victim", -take, counterparty_id=thief_id)
            return True, take
        else:
            fine = max(int(thief.wallet * config.STEAL_FINE_PCT), config.STEAL_MIN_FINE)
            fine = min(fine, thief.wallet)  # never drive below zero
            thief.wallet -= fine
            _record(session, thief, "steal_fine", -fine, counterparty_id=victim_id)
            return False, -fine


# ── coinflip ────────────────────────────────────────────────────────────────

async def coinflip(discord_id: int, amount: int, guess: str) -> tuple[bool, str, int, int]:
    """50/50 with house edge. Returns (won, result_side, net, new_wallet)."""
    guess = guess.lower()
    if guess not in ("heads", "tails", "h", "t"):
        raise EconomyError("Call `heads` or `tails`.")
    guess = "heads" if guess in ("heads", "h") else "tails"

    import random as _r
    result = _r.choice(("heads", "tails"))
    won = result == guess
    # Fair win pays 2x; house edge shaves it.
    multiplier = (2.0 * (1 - config.HOUSE_EDGE)) if won else 0.0
    net, wallet = await settle_bet(discord_id, amount, multiplier)
    return won, result, net, wallet


# ── slots ───────────────────────────────────────────────────────────────────

def _spin_slots() -> list[str]:
    symbols = list(config.SLOTS_SYMBOLS.keys())
    weights = [config.SLOTS_SYMBOLS[s][0] for s in symbols]
    import random as _r
    return _r.choices(symbols, weights=weights, k=3)


async def slots(discord_id: int, amount: int) -> tuple[list[str], int, int]:
    """Spin. Returns (reels, net, new_wallet)."""
    reels = _spin_slots()
    if reels[0] == reels[1] == reels[2]:
        multiplier = float(config.SLOTS_SYMBOLS[reels[0]][1])
    elif reels[0] == reels[1] or reels[1] == reels[2] or reels[0] == reels[2]:
        multiplier = config.SLOTS_TWO_MATCH_MULT
    else:
        multiplier = 0.0
    net, wallet = await settle_bet(discord_id, amount, multiplier)
    return reels, net, wallet


# ── roulette ────────────────────────────────────────────────────────────────

async def roulette(discord_id: int, amount: int, bet: str) -> tuple[int, str, int, int]:
    """Spin roulette. bet is 'red','black', a dozen '1'/'2'/'3', or a number 0-36.

    Returns (result_number, result_desc, net, new_wallet).
    """
    bet = bet.lower().strip()
    import random as _r
    result = _r.randint(0, config.ROULETTE_SLOTS - 1)  # 0..36
    is_red = result != 0 and result % 2 == 1  # simplified red/black

    multiplier = 0.0
    if bet in ("red", "black"):
        if (bet == "red" and is_red) or (bet == "black" and result != 0 and not is_red):
            multiplier = config.ROULETTE_RED_BLACK_MULT * (1 - config.HOUSE_EDGE)
    elif bet in ("1", "2", "3"):  # dozens: 1-12, 13-24, 25-36
        lo = (int(bet) - 1) * 12 + 1
        hi = lo + 11
        if lo <= result <= hi:
            multiplier = config.ROULETTE_DOZEN_MULT * (1 - config.HOUSE_EDGE)
    elif bet.isdigit() and 0 <= int(bet) <= 36:
        if int(bet) == result:
            multiplier = config.ROULETTE_NUMBER_MULT * (1 - config.HOUSE_EDGE)
    else:
        raise EconomyError("Bet on `red`, `black`, a dozen `1`/`2`/`3`, or a number `0`-`36`.")

    net, wallet = await settle_bet(discord_id, amount, multiplier)
    color = "green (0)" if result == 0 else ("red" if is_red else "black")
    return result, color, net, wallet


# ── leaderboard ─────────────────────────────────────────────────────────────

async def leaderboard(limit: int = 10) -> list[tuple[int, int]]:
    """Top players by net worth. Returns [(discord_id, net_worth), ...]."""
    async with get_session() as session:
        repo = EconomyRepository(session)
        players = await repo.top_by_net_worth(limit)
        return [(p.discord_id, p.wallet + p.vault) for p in players]


# ── interactive games ───────────────────────────────────────────────────────


async def escrow_stake(discord_id: int, amount: int) -> str:
    """Deduct the stake at game start (locked). Raises if funds are short.

    Once escrowed the bits have left the wallet, so abandoning the game forfeits
    them — only payout_winnings() can return value, and only for a real win.

    Returns a per-game session id; the game's resolution (payout/forfeit) must
    carry the same id so reconciliation can pair them exactly.
    """
    validate_bet(amount)
    session_id = uuid.uuid4().hex  # 32 chars, fits Transaction.game_session_id
    async with get_session() as session:
        repo = EconomyRepository(session)
        player = await repo.get_or_create_for_update(discord_id)
        if player.wallet < amount:
            raise EconomyError("You don't have that many bits in your wallet.")
        player.wallet -= amount
        _record(session, player, "game_stake", -amount, game_session_id=session_id)
    return session_id


async def payout_winnings(discord_id: int, amount: int, session_id: str | None = None) -> int:
    """Credit winnings at game end (locked). Returns new wallet balance.

    Always writes a game_payout row tagged with the game's session id — even on a
    loss (amount 0) — so the session is marked resolved and reconciliation won't
    mistake a finished game for a stranded one. The wallet only moves on a win.
    """
    async with get_session() as session:
        repo = EconomyRepository(session)
        player = await repo.get_or_create_for_update(discord_id)
        if amount > 0:
            player.wallet += amount
        _record(session, player, "game_payout", amount, game_session_id=session_id)
        return player.wallet


# ── staff-only ledger queries ───────────────────────────────────────────────

async def get_history(discord_id: int, limit: int = 15, offset: int = 0):
    """Recent ledger rows for a user (staff use). Returns (rows, total_count)."""
    async with get_session() as session:
        repo = EconomyRepository(session)
        rows = await repo.recent_transactions(discord_id, limit=limit, offset=offset)
        total = await repo.transaction_count(discord_id)
        return rows, total


async def log_forfeit(discord_id: int, amount: int, game: str,
                      session_id: str | None = None) -> None:
    """Record that an abandoned interactive game forfeited its escrowed stake.

    The bits already left at escrow; this writes the closing ledger entry so the
    audit trail shows the resolution instead of bits silently vanishing. It
    carries the game's session id so reconciliation sees the session as resolved.
    """
    async with get_session() as session:
        repo = EconomyRepository(session)
        player = await repo.get_or_create(discord_id)
        session.add(Transaction(
            discord_id=discord_id,
            kind="game_forfeit",
            amount=0,  # no balance change now; the loss was the earlier game_stake
            balance_after=player.wallet,
            note=f"{game} abandoned; stake forfeited",
            game_session_id=session_id,
        ))


# ── player-facing summaries (own data only) ─────────────────────────────────

async def get_cooldowns(discord_id: int) -> list[tuple[str, str]]:
    """Return [(label, 'ready'|'Xh Ym'), ...] for every faucet/risk cooldown."""
    async with get_session() as session:
        repo = EconomyRepository(session)
        player = await repo.get_or_create(discord_id)
        pairs = [
            ("Daily", _cooldown_remaining(player.last_daily_at, config.DAILY_COOLDOWN)),
            ("Work", _cooldown_remaining(player.last_work_at, config.WORK_COOLDOWN)),
            ("Pray", _cooldown_remaining(player.last_pray_at, config.PRAY_COOLDOWN)),
            ("Steal", _cooldown_remaining(player.last_steal_at, config.STEAL_COOLDOWN)),
        ]
        return [(label, _fmt_remaining(secs)) for label, secs in pairs]


async def get_stats(discord_id: int) -> dict:
    """A player's own headline stats. No ledger detail, no other players' data."""
    async with get_session() as session:
        repo = EconomyRepository(session)
        player = await repo.get_or_create(discord_id)
        rank = await repo.net_worth_rank(discord_id)
        gen_rate = config.GENERATOR_TIERS.get(player.generator_tier, (0, 0))[0]
        return {
            "wallet": player.wallet,
            "vault": player.vault,
            "vault_capacity": player.vault_capacity,
            "net_worth": player.wallet + player.vault,
            "rank": rank,
            "daily_streak": player.daily_streak,
            "generator_tier": player.generator_tier,
            "generator_rate": gen_rate,
        }


# ── startup reconciliation (refund escrows stranded by a restart) ───────────

async def reconcile_stranded_escrows() -> int:
    """Refund stakes whose game never wrote a resolution (mid-game restart).

    A game writes `game_stake` on start (tagged with a session id) and exactly
    one resolution — `game_payout` / `game_forfeit` — on finish, carrying the
    same id. If the bot restarted mid-game the stake left the wallet but no
    resolution was written, so the bits are stranded. Run at startup (when no
    game can legitimately be in-flight): refund every stake whose session has no
    resolution row, each by its own amount.

    Idempotent: the `game_refund` we write is itself a resolution, so a second
    run skips that session. Legacy rows with a NULL session id are ignored (they
    predate session tracking and have nothing to pair against). The query is
    bounded to unresolved sessions rather than scanning the whole ledger.

    Returns the number of stranded sessions refunded.
    """
    from sqlalchemy import exists, select
    from sqlalchemy.orm import aliased

    refunded = 0
    async with get_session() as session:
        resolution = aliased(Transaction)
        stmt = (
            select(Transaction)
            .where(
                Transaction.kind == "game_stake",
                Transaction.game_session_id.is_not(None),
                ~exists(
                    select(resolution.id).where(
                        resolution.game_session_id == Transaction.game_session_id,
                        resolution.kind.in_(
                            ("game_payout", "game_forfeit", "game_refund")
                        ),
                    )
                ),
            )
            .order_by(Transaction.created_at.asc(), Transaction.id.asc())
        )
        stranded = (await session.execute(stmt)).scalars().all()

        repo = EconomyRepository(session)
        for stake in stranded:
            player = await repo.get_or_create_for_update(stake.discord_id)
            player.wallet += -stake.amount  # stake stored negative → positive refund
            _record(session, player, "game_refund", -stake.amount,
                    game_session_id=stake.game_session_id,
                    note="stranded escrow refunded on startup")
            refunded += 1

    return refunded
