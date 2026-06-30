"""Amount converters: let any money command take a number or the word `all`.

These are used as parameter annotations on the economy hybrid commands. Because
they are ``commands.Converter`` subclasses, discord.py renders them as *string*
slash-command options, which is the only reason `all` can be typed on the slash
side at all (an ``int`` option would reject it outright).

`all` (and its synonym `max`) is resolved to one of the author's balances at
convert time, so every command downstream still receives a plain ``int`` and
nothing else has to change. The read is a snapshot: the resolved figure is
re-checked under a row lock by the service before any bits actually move, so a
balance that shifts in between can only cause a clean "not enough bits" error,
never an overdraft.
"""

from __future__ import annotations

from discord.ext import commands

from src.modules.economy import service

_ALL_TOKENS = frozenset({"all", "max"})


# Human shorthand suffixes: 1k = 1,000 · 2m = 2,000,000 · 1b · 1t.
_SUFFIXES = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000, "t": 1_000_000_000_000}


def _parse_int(argument: str) -> int:
    """Parse a whole-number amount, tolerating thousands separators (`1,500`, `1_000`)
    and human shorthand (`1k`, `100k`, `2m`, `2.5m`, `1b`, `1t`; case-insensitive).

    Raises EconomyError (a BotError) so the message reaches the user through the
    normal friendly-error path instead of a generic converter failure. Sign and
    range aren't judged here; the service's validate_amount/validate_bet stay the
    single source of truth for that.
    """
    cleaned = argument.strip().lower().replace(",", "").replace("_", "")
    factor = 1
    if cleaned and cleaned[-1] in _SUFFIXES:
        factor, cleaned = _SUFFIXES[cleaned[-1]], cleaned[:-1]
    try:
        # A decimal only makes sense with a suffix (`2.5k`); a bare `1.5` stays invalid.
        return int(cleaned) if factor == 1 else int(float(cleaned) * factor)
    except ValueError:
        raise service.EconomyError(
            "Amount must be a number like `500`, `1k`, or `2.5m` (or `all`)."
        ) from None


class _BalanceAmount(commands.Converter):
    """A whole-number amount, or `all`/`max` meaning one of the author's pools.

    Subclasses set ``_pool`` to choose which balance `all` expands to.
    """

    _pool = "wallet"
    # Shown when `all`/`max` is used but the chosen pool is empty. Without this we
    # would resolve to 0 and the service would answer "Amount must be positive.",
    # which is baffling to someone who typed a word, not a number.
    _empty_message = "Your wallet is empty."

    async def convert(self, ctx: commands.Context, argument: str) -> int:
        if argument.strip().lower() in _ALL_TOKENS:
            wallet, vault, _cap = await service.get_balance(ctx.author.id)
            value = wallet if self._pool == "wallet" else vault
            if value <= 0:
                raise service.EconomyError(self._empty_message)
            return value
        return _parse_int(argument)


class WalletAmount(_BalanceAmount):
    """`all` / `max` → the author's entire wallet (spends, bets, transfers)."""

    _pool = "wallet"
    _empty_message = "Your wallet is empty."


class VaultAmount(_BalanceAmount):
    """`all` / `max` → the author's entire vault (withdrawals)."""

    _pool = "vault"
    _empty_message = "You have nothing in your vault to withdraw."
