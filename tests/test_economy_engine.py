"""Behavioral tests for the economy money/gambling engine.

Two layers:
  * Pure game logic (no DB, no Discord): blackjack totals, dealer rule, hi-lo
    payout EV. This is the most arithmetic-dense, payout-determining code.
  * DB-backed money mutations against the conftest SQLite: transfer conservation,
    bet net math, staff drain, vault clamping, upgrade cost math, payout
    idempotency, and stranded-escrow refund. These are the integer-truncation /
    negative-balance / double-pay bug classes plain reads can't catch.
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from src.database.base import Base
from src.database.models.transaction import Transaction
from src.database.session import engine, get_session
from src.modules.economy import config, service
from src.modules.economy.games import logic


async def _schema() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def _wallet(uid: int) -> int:
    wallet, _vault, _cap = await service.get_balance(uid)
    return wallet


async def _seed(uid: int, wallet: int) -> None:
    """Give a player a known wallet balance via the staff faucet."""
    await service.staff_grant(uid, wallet, staff_id=1)


async def _count(session_id: str, *kinds: str) -> int:
    async with get_session() as session:
        stmt = select(func.count()).select_from(Transaction).where(
            Transaction.game_session_id == session_id,
            Transaction.kind.in_(kinds),
        )
        return int((await session.execute(stmt)).scalar_one())


# ── pure game logic (finding 3) ─────────────────────────────────────────────

def test_hand_total_softens_aces():
    # rank is all that matters; suit is cosmetic.
    assert logic.hand_total([("A", "s"), ("A", "h"), ("9", "d")]) == 21  # 11+1+9
    assert logic.hand_total([("A", "s"), ("A", "h")]) == 12              # 11+1
    assert logic.hand_total([("A", "s"), ("K", "h")]) == 21             # 11+10
    assert logic.hand_total([("A", "s"), ("A", "h"), ("A", "d")]) == 13  # 11+1+1


def test_hand_total_hard_hands():
    assert logic.hand_total([("K", "s"), ("Q", "h")]) == 20
    assert logic.hand_total([("K", "s"), ("Q", "h"), ("5", "d")]) == 25  # bust, no aces


def test_is_blackjack_only_two_cards():
    assert logic.is_blackjack([("A", "s"), ("K", "h")]) is True
    # 21 on three cards is not a blackjack.
    assert logic.is_blackjack([("7", "s"), ("7", "h"), ("7", "d")]) is False
    assert logic.is_blackjack([("A", "s"), ("9", "h")]) is False


def test_dealer_play_stops_at_17():
    # Stacked deck: dealer starts on 16 (10 + 6), draws once, then stands on 17+.
    # deck.pop() draws from the end, so the next card is the last element.
    g = logic.BlackjackGame(
        deck=[("9", "s"), ("5", "h")],  # 5 drawn first -> 16+5 = 21, stands
        player=[("2", "s"), ("3", "h")],
        dealer=[("10", "d"), ("6", "c")],  # 16
    )
    g.dealer_play()
    assert logic.hand_total(g.dealer) >= 17


def test_dealer_play_no_draw_when_already_17():
    g = logic.BlackjackGame(
        deck=[("9", "s")],
        player=[("2", "s"), ("3", "h")],
        dealer=[("10", "d"), ("7", "c")],  # 17 -> stands immediately
    )
    g.dealer_play()
    assert len(g.dealer) == 2  # no card drawn
    assert logic.hand_total(g.dealer) == 17


def test_hilo_multipliers_inverse_probability():
    # current=1 (a '2'): p_higher = 13/13 = 1.0, p_lower = 1/13.
    higher, lower = logic.hilo_multipliers(1, 0.0)
    assert higher == pytest.approx(1.0)
    assert lower == pytest.approx(13.0)
    # The shaved edge makes EV per pick = 1 - house_edge on the winning side.
    edge = 0.02
    higher_e, lower_e = logic.hilo_multipliers(7, edge)
    p_higher = (14 - 7) / 13
    p_lower = 7 / 13
    assert higher_e * p_higher == pytest.approx(1 - edge)
    assert lower_e * p_lower == pytest.approx(1 - edge)


def test_hilo_face_roundtrip():
    assert logic.hilo_face(1) == "2"
    assert logic.hilo_face(13) == "A"


# ── give: conservation, self-give, insufficient funds (finding 2) ────────────

async def test_give_conserves_total_and_moves_bits():
    await _schema()
    a, b = 910_000_001, 910_000_002
    await _seed(a, 1000)
    await _seed(b, 200)
    await service.give(a, b, 300)
    assert await _wallet(a) == 700
    assert await _wallet(b) == 500  # total conserved: 1200 before and after


async def test_give_rejects_self():
    await _schema()
    a = 910_000_003
    await _seed(a, 1000)
    with pytest.raises(service.EconomyError, match="yourself"):
        await service.give(a, a, 100)
    assert await _wallet(a) == 1000


async def test_give_rejects_insufficient_funds():
    await _schema()
    a, b = 910_000_004, 910_000_005
    await _seed(a, 50)
    with pytest.raises(service.EconomyError, match="enough"):
        await service.give(a, b, 100)
    assert await _wallet(a) == 50
    assert await _wallet(b) == 0


async def test_give_enforces_min(monkeypatch):
    # GIVE_MIN is enforced (finding 5): raising it above 1 must take effect.
    await _schema()
    a, b = 910_000_006, 910_000_007
    await _seed(a, 1000)
    monkeypatch.setattr(config, "GIVE_MIN", 100)
    with pytest.raises(service.EconomyError, match="at least"):
        await service.give(a, b, 50)
    assert await _wallet(a) == 1000


# ── settle_bet: net math across multipliers, stake bound (finding 2) ─────────

async def test_settle_bet_total_loss():
    await _schema()
    uid = 911_000_001
    await _seed(uid, 1000)
    net, wallet = await service.settle_bet(uid, 100, 0.0)
    assert net == -100              # lost the whole stake
    assert wallet == 900


async def test_settle_bet_double():
    await _schema()
    uid = 911_000_002
    await _seed(uid, 1000)
    net, wallet = await service.settle_bet(uid, 100, 2.0)
    assert net == 100               # payout 200 - stake 100
    assert wallet == 1100


async def test_settle_bet_fractional_truncates():
    await _schema()
    uid = 911_000_003
    await _seed(uid, 1000)
    # payout = int(100 * 1.5) = 150; net = 50.
    net, wallet = await service.settle_bet(uid, 100, 1.5)
    assert net == 50
    assert wallet == 1050


async def test_settle_bet_rejects_stake_over_wallet():
    await _schema()
    uid = 911_000_004
    await _seed(uid, 50)
    with pytest.raises(service.EconomyError, match="that many"):
        await service.settle_bet(uid, 100, 2.0)
    assert await _wallet(uid) == 50


# ── staff_deduct: wallet-then-vault drain, both stay >= 0 (finding 2) ────────

async def test_staff_deduct_drains_wallet_then_vault():
    await _schema()
    uid = 912_000_001
    await _seed(uid, 1000)
    await service.deposit(uid, 400)  # wallet 600, vault 400
    from_wallet, from_vault = await service.staff_deduct(uid, 800, staff_id=1)
    assert from_wallet == 600
    assert from_vault == 200
    wallet, vault, _cap = await service.get_balance(uid)
    assert wallet == 0
    assert vault == 200  # both pools non-negative


async def test_staff_deduct_caps_at_holdings():
    await _schema()
    uid = 912_000_002
    await _seed(uid, 300)
    from_wallet, from_vault = await service.staff_deduct(uid, 10_000, staff_id=1)
    assert from_wallet == 300
    assert from_vault == 0
    assert await _wallet(uid) == 0


async def test_staff_deduct_rejects_when_nothing_to_take():
    await _schema()
    uid = 912_000_003  # fresh: wallet and vault both 0
    with pytest.raises(service.EconomyError, match="no bits"):
        await service.staff_deduct(uid, 100, staff_id=1)


# ── deposit / withdraw: capacity clamping (finding 2) ────────────────────────

async def test_deposit_clamps_to_capacity():
    await _schema()
    uid = 913_000_001
    cap = config.VAULT_BASE_CAPACITY
    await _seed(uid, cap + 5000)
    moved = await service.deposit(uid, cap + 5000)
    assert moved == cap                          # only capacity fit
    wallet, vault, _cap = await service.get_balance(uid)
    assert vault == cap
    assert wallet == 5000                         # the overflow stayed in the wallet


async def test_deposit_rejects_when_full():
    await _schema()
    uid = 913_000_002
    cap = config.VAULT_BASE_CAPACITY
    await _seed(uid, cap + 100)
    await service.deposit(uid, cap)               # vault now full
    with pytest.raises(service.EconomyError, match="full"):
        await service.deposit(uid, 100)


async def test_withdraw_moves_back_and_rejects_overdraw():
    await _schema()
    uid = 913_000_003
    await _seed(uid, 1000)
    await service.deposit(uid, 600)               # vault 600, wallet 400
    out = await service.withdraw(uid, 250)
    assert out == 250
    wallet, vault, _cap = await service.get_balance(uid)
    assert wallet == 650
    assert vault == 350
    with pytest.raises(service.EconomyError, match="that many"):
        await service.withdraw(uid, 10_000)


# ── upgrade cost math (finding 2) ────────────────────────────────────────────

async def test_upgrade_vault_pays_the_difference():
    await _schema()
    uid = 914_000_001
    # Tier 0 -> 1 costs the cumulative difference 25_000 - 0.
    _next_cap, cost = config.VAULT_TIERS[1]
    await _seed(uid, cost + 500)
    new_cap, paid = await service.upgrade_vault(uid)
    assert paid == cost
    assert new_cap == config.VAULT_TIERS[1][0]
    assert await _wallet(uid) == 500


async def test_upgrade_vault_rejects_when_short():
    await _schema()
    uid = 914_000_002
    _cap, cost = config.VAULT_TIERS[1]
    await _seed(uid, cost - 1)
    with pytest.raises(service.EconomyError, match="need"):
        await service.upgrade_vault(uid)
    assert await _wallet(uid) == cost - 1  # nothing charged


async def test_upgrade_generator_auto_claims_then_charges():
    await _schema()
    uid = 914_000_003
    # Buy tier 1 first so there's a rate to accrue against.
    rate1, cost1 = config.GENERATOR_TIERS[1]
    rate2, cost2 = config.GENERATOR_TIERS[2]
    await _seed(uid, cost1 + cost2 + 50_000)
    await service.upgrade_generator(uid)          # now tier 1, claimed_at = now

    # Backdate the claim so a known amount has accrued, then upgrade again.
    from datetime import timedelta
    async with get_session() as session:
        from src.modules.economy.repository import EconomyRepository
        player = await EconomyRepository(session).get_for_update(uid)
        player.generator_claimed_at = service._now() - timedelta(hours=2)
    pending = rate1 * 2  # 2 hours at tier-1 rate, well under the cap

    before = await _wallet(uid)
    new_tier, new_rate, paid = await service.upgrade_generator(uid)
    assert new_tier == 2
    assert new_rate == rate2
    assert paid == cost2
    # Pending was credited before the rate changed, then the cost was charged.
    assert await _wallet(uid) == before + pending - cost2


# ── payout_winnings idempotency (finding 1 + 4) ──────────────────────────────

async def test_payout_winnings_is_idempotent_on_win():
    await _schema()
    uid = 915_000_001
    await _seed(uid, 1000)
    sid = await service.escrow_stake(uid, 100)    # wallet 900, stake escrowed
    w1 = await service.payout_winnings(uid, 300, sid)
    assert w1 == 1200
    # A second (raced) click for the same session must NOT pay again.
    w2 = await service.payout_winnings(uid, 300, sid)
    assert w2 == 1200
    assert await _wallet(uid) == 1200
    assert await _count(sid, "game_payout") == 1   # only one resolution row


async def test_payout_winnings_is_idempotent_on_loss():
    await _schema()
    uid = 915_000_002
    await _seed(uid, 1000)
    sid = await service.escrow_stake(uid, 100)
    await service.payout_winnings(uid, 0, sid)     # loss resolution
    await service.payout_winnings(uid, 0, sid)     # stray queued click
    assert await _wallet(uid) == 900
    assert await _count(sid, "game_payout") == 1


async def test_forfeit_after_payout_does_not_double_resolve():
    await _schema()
    uid = 915_000_003
    await _seed(uid, 1000)
    sid = await service.escrow_stake(uid, 100)
    await service.payout_winnings(uid, 300, sid)   # resolved as a win
    # on_timeout fires later and tries to forfeit; the session is already resolved.
    await service.log_forfeit(uid, 100, "crash", sid)
    assert await _wallet(uid) == 1200
    assert await _count(sid, "game_payout", "game_forfeit") == 1


# ── reconcile_stranded_escrows: refund once, idempotent (finding 2) ──────────

async def test_reconcile_refunds_stranded_stake_once():
    await _schema()
    uid = 916_000_001
    await _seed(uid, 1000)
    await service.escrow_stake(uid, 250)           # stake left, no resolution written
    assert await _wallet(uid) == 750

    refunded = await service.reconcile_stranded_escrows()
    assert refunded >= 1
    assert await _wallet(uid) == 1000              # stake returned

    # Second run is a no-op for this session (the refund is itself a resolution).
    await service.reconcile_stranded_escrows()
    assert await _wallet(uid) == 1000
    # The refund row exists exactly once for this user's stranded stake.
    async with get_session() as session:
        stmt = select(func.count()).select_from(Transaction).where(
            Transaction.discord_id == uid,
            Transaction.kind == "game_refund",
        )
        assert int((await session.execute(stmt)).scalar_one()) == 1


async def test_reconcile_skips_resolved_session():
    await _schema()
    uid = 916_000_002
    await _seed(uid, 1000)
    sid = await service.escrow_stake(uid, 200)
    await service.payout_winnings(uid, 0, sid)     # already resolved (loss)
    wallet_before = await _wallet(uid)             # 800

    await service.reconcile_stranded_escrows()
    assert await _wallet(uid) == wallet_before     # not refunded
