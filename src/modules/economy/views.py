"""Interactive economy panels: gamble re-bet, the profile hub, vault/generator
control panels, and a give/steal confirmation.

State lives in the DB (the service owns the money); these views only re-call the
existing service functions and re-render. Every view is invoker-locked via
``OwnerView`` and greys its controls on timeout. The one-shot game embeds are built
by the ``play_*`` helpers so both the command and the "Play again" button share one
code path.
"""

from __future__ import annotations

import time

import discord

from src.core import embeds
from src.core.emojis import Emojis
from src.core.views import OwnerView
from src.modules.economy import config, service

_REBET_DEBOUNCE = 1.5  # seconds; component clicks bypass the command's cooldown


def _fmt(n: int) -> str:
    return f"{n:,}"


# ── one-shot game result embeds (shared by command + re-bet button) ──────────

async def play_coinflip(player_id: int, amount: int, call: str) -> discord.Embed:
    won, result, net, wallet = await service.coinflip(player_id, amount, call)
    verb = "won" if won else "lost"
    return (embeds.success if won else embeds.error)(
        f"{Emojis.COIN_FLIP} It landed **{result}**. You {verb} "
        f"{Emojis.BITS} **{_fmt(abs(net))}**.\nWallet: {_fmt(wallet)}"
    )


async def play_slots(player_id: int, amount: int) -> discord.Embed:
    reels, net, wallet = await service.slots(player_id, amount)
    won = net > 0
    body = (f"You won {Emojis.BITS} **{_fmt(net)}**!" if won
            else f"You lost {Emojis.BITS} **{_fmt(abs(net))}**.")
    return (embeds.success if won else embeds.error)(
        f"{Emojis.SLOTS} [ {' '.join(reels)} ]\n{body}\nWallet: {_fmt(wallet)}"
    )


async def play_roulette(player_id: int, amount: int, bet: str) -> discord.Embed:
    result, color, net, wallet = await service.roulette(player_id, amount, bet)
    won = net > 0
    body = (f"You won {Emojis.BITS} **{_fmt(net)}**!" if won
            else f"You lost {Emojis.BITS} **{_fmt(amount)}**.")
    return (embeds.success if won else embeds.error)(
        f"{Emojis.DICE} The ball landed on **{result}** ({color}).\n{body}\nWallet: {_fmt(wallet)}"
    )


async def play_dice(player_id: int, amount: int, target: int) -> discord.Embed:
    won, roll, target, net, wallet = await service.dice(player_id, amount, target)
    body = (f"You won {Emojis.BITS} **{_fmt(net)}**!" if won
            else f"You lost {Emojis.BITS} **{_fmt(amount)}**.")
    return (embeds.success if won else embeds.error)(
        f"{Emojis.DICE} Rolled **{roll}** vs target **{target}**.\n{body}\nWallet: {_fmt(wallet)}"
    )


async def play_limbo(player_id: int, amount: int, target: float) -> discord.Embed:
    won, outcome, target, net, wallet = await service.limbo(player_id, amount, target)
    body = (f"You won {Emojis.BITS} **{_fmt(net)}**!" if won
            else f"You lost {Emojis.BITS} **{_fmt(amount)}**.")
    return (embeds.success if won else embeds.error)(
        f"{Emojis.DICE} Round hit **{outcome:.2f}x** (target **{target:.2f}x**).\n"
        f"{body}\nWallet: {_fmt(wallet)}"
    )


async def play_plinko(player_id: int, amount: int) -> discord.Embed:
    bucket, path, mult, net, wallet = await service.plinko(player_id, amount)
    won = net > 0
    row = " ".join(
        f"[{m:g}]" if i == bucket else f"{m:g}"
        for i, m in enumerate(config.PLINKO_MULTIPLIERS)
    )
    body = (f"You won {Emojis.BITS} **{_fmt(net)}**!" if won
            else f"You lost {Emojis.BITS} **{_fmt(abs(net))}**.")
    return (embeds.success if won else embeds.error)(
        f"{Emojis.SLOTS} {row}\nPath: {' '.join(path)} -> **{mult:.2f}x**\n"
        f"{body}\nWallet: {_fmt(wallet)}"
    )


# ── status embeds (shared by command + panel refresh) ────────────────────────

async def render_profile(user: discord.abc.User, *, note: str = "") -> discord.Embed:
    p = await service.get_profile(user.id)
    rank = f"#{p['rank']}" if p["rank"] else "Unranked"
    e = embeds.info(note, f"{Emojis.RANK} {user.display_name}'s Profile")
    e.add_field(name="Net Worth", value=f"{Emojis.BITS} {_fmt(p['net_worth'])}")
    e.add_field(name="Wealth Rank", value=rank)
    e.add_field(name="Daily Streak", value=f"{Emojis.FIRE} {p['daily_streak']}")
    e.add_field(name="Wallet", value=f"{Emojis.BITS} {_fmt(p['wallet'])}")
    e.add_field(
        name="Vault", value=f"{Emojis.BANK} {_fmt(p['vault'])} / {_fmt(p['vault_capacity'])}"
    )
    if p["generator_tier"] > 0:
        e.add_field(
            name="Generator",
            value=f"T{p['generator_tier']} · {_fmt(p['generator_rate'])}/hr "
                  f"(+{_fmt(p['generator_pending'])} pending)",
        )
    cd = " · ".join(f"{label}: {status}" for label, status in p["cooldowns"])
    e.add_field(name="Cooldowns", value=cd, inline=False)
    return e


async def render_vault(user: discord.abc.User, *, note: str = "") -> discord.Embed:
    _w, v, cap = await service.get_balance(user.id)
    info = service.vault_upgrade_info(cap)
    e = embeds.info(note, f"{Emojis.BANK} Your Vault")
    e.add_field(name="Stored", value=f"{_fmt(v)} / {_fmt(cap)}", inline=False)
    if info is None:
        e.add_field(name="Upgrade", value="Maxed out.", inline=False)
    else:
        next_cap, cost = info
        e.add_field(
            name="Next upgrade",
            value=f"Capacity {_fmt(next_cap)} for {Emojis.BITS} {_fmt(cost)}",
            inline=False,
        )
    return e


async def render_generator(user: discord.abc.User, *, note: str = "") -> discord.Embed:
    tier, rate, pending = await service.get_generator(user.id)
    e = embeds.info(note, f"{Emojis.SETTINGS} Your Generator")
    if tier <= 0:
        up = service.generator_upgrade_info(0)
        if not note:
            e.description = "You don't own a generator yet."
        if up:
            nt, nr, cost = up
            e.add_field(
                name="Buy one",
                value=f"Tier {nt}: {_fmt(nr)}/hr for {Emojis.BITS} {_fmt(cost)}",
                inline=False,
            )
        return e
    e.add_field(name="Tier", value=str(tier))
    e.add_field(name="Rate", value=f"{_fmt(rate)}/hr")
    e.add_field(name="Pending", value=f"{Emojis.BITS} {_fmt(pending)}")
    up = service.generator_upgrade_info(tier)
    if up:
        nt, nr, cost = up
        e.add_field(
            name="Next tier",
            value=f"Tier {nt}: {_fmt(nr)}/hr for {Emojis.BITS} {_fmt(cost)}",
            inline=False,
        )
    return e


# ── re-bet on the one-shot gambles ───────────────────────────────────────────

class RebetView(OwnerView):
    """A result panel with Play again / Double, re-running the same wager in place."""

    def __init__(self, player_id: int, amount: int, replay, *, invoker) -> None:
        super().__init__(player_id, invoker=invoker)
        self._amount = amount
        self._replay = replay  # async (amount: int) -> discord.Embed
        self._busy = False
        self._last = 0.0

    async def _bet(self, interaction: discord.Interaction, amount: int) -> None:
        now = time.monotonic()
        if self._busy or now - self._last < _REBET_DEBOUNCE:
            await interaction.response.defer()
            return
        self._busy = True
        try:
            embed = await self._replay(amount)
        except service.EconomyError as exc:
            for child in self.children:
                child.disabled = True
            self.stop()
            await interaction.response.edit_message(embed=embeds.error(str(exc)), view=self)
            return
        finally:
            self._busy = False
        self._last = time.monotonic()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Play again", emoji=Emojis.DICE, style=discord.ButtonStyle.success)
    async def _again(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self._bet(interaction, self._amount)

    @discord.ui.button(label="Double", style=discord.ButtonStyle.primary)
    async def _double(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self._bet(interaction, self._amount * 2)


# ── vault panel ──────────────────────────────────────────────────────────────

class VaultView(OwnerView):
    def __init__(self, user: discord.abc.User, *, invoker) -> None:
        super().__init__(user.id, invoker=invoker)
        self._user = user

    @discord.ui.button(label="Upgrade", emoji=Emojis.BANK, style=discord.ButtonStyle.success)
    async def _upgrade(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        try:
            new_cap, cost = await service.upgrade_vault(self._user.id)
        except service.EconomyError as exc:
            await interaction.response.send_message(embed=embeds.error(str(exc)), ephemeral=True)
            return
        note = (f"{Emojis.SUCCESS} Upgraded to {_fmt(new_cap)} capacity "
                f"for {Emojis.BITS} {_fmt(cost)}")
        await interaction.response.edit_message(
            embed=await render_vault(self._user, note=note), view=self
        )

    @discord.ui.button(label="Refresh", emoji=Emojis.LOADING, style=discord.ButtonStyle.secondary)
    async def _refresh_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await interaction.response.edit_message(
            embed=await render_vault(self._user), view=self
        )


# ── generator panel ──────────────────────────────────────────────────────────

class GeneratorView(OwnerView):
    def __init__(self, user: discord.abc.User, *, invoker) -> None:
        super().__init__(user.id, invoker=invoker)
        self._user = user

    @discord.ui.button(label="Claim", emoji=Emojis.BITS, style=discord.ButtonStyle.success)
    async def _claim(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        amount = await service.claim_generator(self._user.id)
        note = f"{Emojis.BITS} Collected {_fmt(amount)}"
        await interaction.response.edit_message(
            embed=await render_generator(self._user, note=note), view=self
        )

    @discord.ui.button(label="Upgrade", emoji=Emojis.SETTINGS, style=discord.ButtonStyle.primary)
    async def _upgrade(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        try:
            tier, rate, cost = await service.upgrade_generator(self._user.id)
        except service.EconomyError as exc:
            await interaction.response.send_message(embed=embeds.error(str(exc)), ephemeral=True)
            return
        note = f"{Emojis.SUCCESS} Tier {tier} · {_fmt(rate)}/hr for {Emojis.BITS} {_fmt(cost)}"
        await interaction.response.edit_message(
            embed=await render_generator(self._user, note=note), view=self
        )

    @discord.ui.button(label="Refresh", emoji=Emojis.LOADING, style=discord.ButtonStyle.secondary)
    async def _refresh_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await interaction.response.edit_message(
            embed=await render_generator(self._user), view=self
        )


# ── confirm gate (give / steal) ──────────────────────────────────────────────

class ConfirmView(OwnerView):
    """Confirm/Cancel before an action runs. ``action`` is an async callable that
    performs the move and returns the result embed."""

    def __init__(self, player_id: int, action, *, invoker, confirm_label: str = "Confirm") -> None:
        super().__init__(player_id, invoker=invoker)
        self._action = action
        self._confirm.label = confirm_label

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success)
    async def _confirm(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        for child in self.children:
            child.disabled = True
        try:
            embed = await self._action()
        except service.EconomyError as exc:
            embed = embeds.error(str(exc))
        self.stop()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Cancel", emoji=Emojis.CLOSE, style=discord.ButtonStyle.secondary)
    async def _cancel(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        for child in self.children:
            child.disabled = True
        self.stop()
        await interaction.response.edit_message(embed=embeds.info("Cancelled."), view=self)
