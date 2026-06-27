"""Behavioral tests for the `all` amount support and the wallet aliases.

These cover the seam added so every money command accepts `all`/`max`: the
converters that turn a raw argument into a concrete int, and the alias wiring on
the wallet command. The DB-backed cases run against the sqlite file the conftest
points the app at.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.database.base import Base
from src.database.session import engine
from src.modules.economy import service
from src.modules.economy.converters import VaultAmount, WalletAmount


async def _schema() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def _ctx(uid: int) -> SimpleNamespace:
    """Minimal stand-in for a Context — the converter only reads ctx.author.id."""
    return SimpleNamespace(author=SimpleNamespace(id=uid))


# ── parsing (no DB needed) ──────────────────────────────────────────────────

async def test_parses_plain_integer():
    assert await WalletAmount().convert(_ctx(1), "500") == 500


async def test_parses_thousands_separators():
    conv = WalletAmount()
    assert await conv.convert(_ctx(1), "1,500") == 1500
    assert await conv.convert(_ctx(1), "1_000") == 1000


async def test_rejects_non_number():
    with pytest.raises(service.EconomyError):
        await WalletAmount().convert(_ctx(1), "abc")


async def test_garbage_is_not_silently_zero():
    # "all" with a typo must error, not resolve to some balance.
    with pytest.raises(service.EconomyError):
        await WalletAmount().convert(_ctx(1), "alll")


# ── `all` / `max` resolution (DB-backed) ────────────────────────────────────

async def test_all_resolves_to_wallet():
    await _schema()
    uid = 900_000_001
    await service.staff_grant(uid, 4242, staff_id=1)  # wallet = 4242
    conv = WalletAmount()
    assert await conv.convert(_ctx(uid), "all") == 4242
    assert await conv.convert(_ctx(uid), "MAX") == 4242  # synonym + case-insensitive


async def test_all_resolves_to_vault_not_wallet():
    await _schema()
    uid = 900_000_002
    await service.staff_grant(uid, 5000, staff_id=1)
    await service.deposit(uid, 1500)  # vault = 1500, wallet = 3500
    assert await VaultAmount().convert(_ctx(uid), "all") == 1500
    # Same player, wallet converter sees the wallet side instead.
    assert await WalletAmount().convert(_ctx(uid), "all") == 3500


async def test_all_on_empty_pool_gives_pool_specific_message():
    await _schema()
    uid = 900_000_003  # fresh player → wallet and vault both 0
    # `all` on an empty pool must explain the pool is empty, not "Amount must be
    # positive" (which reads as if the user typed a bad number).
    with pytest.raises(service.EconomyError, match="wallet is empty"):
        await WalletAmount().convert(_ctx(uid), "all")
    with pytest.raises(service.EconomyError, match="nothing in your vault"):
        await VaultAmount().convert(_ctx(uid), "max")


# ── alias wiring ────────────────────────────────────────────────────────────

async def test_wallet_has_balance_aliases():
    from src.core.bot import Bot

    await _schema()
    bot = Bot()
    try:
        await bot.load_extension("src.modules.economy.cog")
        wallet_cmd = bot.get_command("wallet")
        assert wallet_cmd is not None
        assert bot.get_command("bal") is wallet_cmd
        assert bot.get_command("balance") is wallet_cmd
    finally:
        for ext in list(bot.extensions):
            await bot.unload_extension(ext)
