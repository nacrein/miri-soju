"""Economy commands: wallet, faucets, give, vault/generator, gambling, profile.

Money logic lives in the service; this cog is the Discord surface. Interactive panels
(re-bet on the one-shot gambles, the profile hub, the vault/generator control panels,
and the give/steal confirm) live in views.py and are reused here. Vault and generator
are single commands whose actions are buttons, not subcommands.
"""

from __future__ import annotations

import logging

import discord
from discord.ext import commands

from src.core import embeds
from src.core.emojis import Emojis
from src.core.errors import SilentError
from src.modules.economy import config, service
from src.modules.economy import views as econ_views
from src.modules.economy.agreement import AgreementView, agreement_embed
from src.modules.economy.converters import VaultAmount, WalletAmount
from src.modules.economy.games.views import BlackjackView, CrashView, HiLoView, LadderView

log = logging.getLogger(__name__)


def _fmt(n: int) -> str:
    return f"{n:,}"


class Economy(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        """Refund game stakes stranded by a previous restart. Non-fatal; runs
        once when the cog loads: the DB is ready and no gateway is needed."""
        try:
            count = await service.reconcile_stranded_escrows()
            if count:
                log.info("Reconciled %d stranded game escrow(s) on startup", count)
        except Exception:
            log.exception("Economy escrow reconciliation failed (continuing)")

    async def cog_check(self, ctx: commands.Context) -> bool:
        """Gate every economy command behind a one-time rules agreement.

        Runs before argument parsing and the command callback, so a command whose body
        would open a view/modal never starts until the user has agreed — no half-opened
        state. ``SilentError`` aborts cleanly after the prompt is posted (the error
        handler swallows it, so the prompt is the only message)."""
        if await service.has_agreed(ctx.author.id):
            return True
        view = AgreementView(ctx.author.id, invoker=ctx.author)
        await view.start(ctx, agreement_embed())
        raise SilentError()

    # ── balances ──────────────────────────────────────────────────────────────

    @commands.command(
        name="wallet", aliases=["bal", "balance"], extras={"example": "wallet @user"}
    )
    @commands.guild_only()
    async def wallet(self, ctx: commands.Context, user: discord.User | None = None) -> None:
        """Show your bits, or someone else's."""
        target = user or ctx.author
        w, v, cap = await service.get_balance(target.id)
        e = embeds.info("", f"{Emojis.BITS} {target.display_name}'s Bits")
        e.add_field(name="Wallet", value=f"{Emojis.BITS} {_fmt(w)}")
        e.add_field(name="Vault", value=f"{Emojis.BANK} {_fmt(v)} / {_fmt(cap)}")
        e.add_field(name="Net Worth", value=f"{_fmt(w + v)}", inline=False)
        await ctx.send(embed=e)

    @commands.command(name="profile", aliases=["p"])
    @commands.guild_only()
    async def profile(self, ctx: commands.Context, user: discord.User | None = None) -> None:
        """Your full economy card: balances, wealth rank, streak, generator, cooldowns."""
        target = user or ctx.author
        await ctx.send(embed=await econ_views.render_profile(target))

    # ── faucets ───────────────────────────────────────────────────────────────

    @commands.cooldown(rate=1, per=config.FAUCET_COOLDOWN_SECONDS, type=commands.BucketType.user)
    @commands.hybrid_command(name="daily")
    @commands.guild_only()
    async def daily(self, ctx: commands.Context) -> None:
        """Claim your daily bits. Keep a streak for bigger rewards."""
        amount, streak = await service.claim_daily(ctx.author.id)
        await ctx.send(
            embed=embeds.success(
                f"You claimed {Emojis.BITS} **{_fmt(amount)}**!\n"
                f"{Emojis.FIRE} Streak: day **{streak}**",
                "Daily Claimed",
            )
        )

    @commands.cooldown(rate=1, per=config.FAUCET_COOLDOWN_SECONDS, type=commands.BucketType.user)
    @commands.command(name="work")
    @commands.guild_only()
    async def work(self, ctx: commands.Context) -> None:
        """Work for some bits."""
        amount = await service.work(ctx.author.id)
        await ctx.send(
            embed=embeds.success(f"You earned {Emojis.BITS} **{_fmt(amount)}** working.")
        )

    @commands.cooldown(rate=1, per=config.FAUCET_COOLDOWN_SECONDS, type=commands.BucketType.user)
    @commands.command(name="pray")
    @commands.guild_only()
    async def pray(self, ctx: commands.Context) -> None:
        """Pray for bits. Sometimes the heavens are generous."""
        amount, blessing = await service.pray(ctx.author.id)
        if blessing:
            msg = f"{Emojis.WIN} A blessing! You received {Emojis.BITS} **{_fmt(amount)}**!"
        else:
            msg = f"You received {Emojis.BITS} **{_fmt(amount)}**."
        await ctx.send(embed=embeds.success(msg))

    @commands.cooldown(rate=1, per=config.BEG_COOLDOWN_SECONDS, type=commands.BucketType.user)
    @commands.command(name="beg")
    @commands.guild_only()
    async def beg(self, ctx: commands.Context) -> None:
        """Beg for a few bits. Sometimes you get nothing."""
        amount, ok = await service.beg(ctx.author.id)
        if ok:
            await ctx.send(
                embed=embeds.success(f"Someone tossed you {Emojis.BITS} **{_fmt(amount)}**.")
            )
        else:
            await ctx.send(embed=embeds.info("Nobody spared you any bits. Try again later."))

    # ── transfers ───────────────────────────────────────────────────────────────

    @commands.command(name="give", extras={"example": "give @user all"})
    @commands.guild_only()
    async def give(self, ctx: commands.Context, user: discord.User, amount: WalletAmount) -> None:
        """Give bits from your wallet to another player. Confirms before sending."""

        async def _send() -> discord.Embed:
            await service.give(ctx.author.id, user.id, amount)
            return embeds.success(
                f"You gave {Emojis.BITS} **{_fmt(amount)}** to {user.mention}."
            )

        view = econ_views.ConfirmView(ctx.author.id, _send, invoker=ctx.author)
        prompt = embeds.warning(f"Give {Emojis.BITS} **{_fmt(amount)}** to {user.mention}?")
        view.message = await ctx.send(embed=prompt, view=view)

    @commands.command(name="deposit", aliases=["dep"], extras={"example": "deposit all"})
    @commands.guild_only()
    async def deposit(self, ctx: commands.Context, amount: WalletAmount) -> None:
        """Move bits from your wallet into your safe vault. Use `all` to deposit everything."""
        moved = await service.deposit(ctx.author.id, amount)
        await ctx.send(
            embed=embeds.success(f"Deposited {Emojis.BANK} **{_fmt(moved)}** into your vault.")
        )

    @commands.command(name="withdraw", aliases=["with"], extras={"example": "withdraw all"})
    @commands.guild_only()
    async def withdraw(self, ctx: commands.Context, amount: VaultAmount) -> None:
        """Move bits from your vault back into your wallet. Use `all` to withdraw everything."""
        moved = await service.withdraw(ctx.author.id, amount)
        await ctx.send(
            embed=embeds.success(f"Withdrew {Emojis.BITS} **{_fmt(moved)}** to your wallet.")
        )

    # ── vault + generator (panels with action buttons) ──────────────────────────

    @commands.command(name="vault")
    @commands.guild_only()
    async def vault(self, ctx: commands.Context) -> None:
        """View your vault and upgrade its capacity with a button."""
        view = econ_views.VaultView(ctx.author, invoker=ctx.author)
        view.message = await ctx.send(embed=await econ_views.render_vault(ctx.author), view=view)

    @commands.command(name="generator", aliases=["gen"])
    @commands.guild_only()
    async def generator(self, ctx: commands.Context) -> None:
        """View your passive generator; claim or upgrade it with buttons."""
        view = econ_views.GeneratorView(ctx.author, invoker=ctx.author)
        view.message = await ctx.send(
            embed=await econ_views.render_generator(ctx.author), view=view
        )

    # ── steal ───────────────────────────────────────────────────────────────────

    @commands.command(name="steal", extras={"example": "steal @user"})
    @commands.guild_only()
    async def steal(self, ctx: commands.Context, user: discord.User) -> None:
        """Attempt to steal bits from someone's wallet. Confirms before the attempt."""

        async def _attempt() -> discord.Embed:
            success, delta = await service.steal(ctx.author.id, user.id)
            if success:
                return embeds.success(
                    f"{Emojis.WIN} You stole {Emojis.BITS} **{_fmt(delta)}** from {user.mention}!"
                )
            return embeds.error(
                f"You got caught and paid a fine of {Emojis.BITS} **{_fmt(-delta)}**."
            )

        view = econ_views.ConfirmView(
            ctx.author.id, _attempt, invoker=ctx.author, confirm_label="Attempt"
        )
        prompt = embeds.warning(f"Attempt to steal from {user.mention}? It's risky.")
        view.message = await ctx.send(embed=prompt, view=view)

    # ── one-shot gambling (Play again / Double) ──────────────────────────────────

    @commands.cooldown(rate=1, per=3.0, type=commands.BucketType.user)
    @commands.command(name="coinflip", aliases=["cf"], extras={"example": "coinflip all heads"})
    @commands.guild_only()
    async def coinflip(self, ctx: commands.Context, amount: WalletAmount, call: str) -> None:
        """Bet on a coin flip. Call heads or tails."""
        embed = await econ_views.play_coinflip(ctx.author.id, amount, call)
        view = econ_views.RebetView(
            ctx.author.id, amount,
            lambda amt: econ_views.play_coinflip(ctx.author.id, amt, call), invoker=ctx.author,
        )
        view.message = await ctx.send(embed=embed, view=view)

    @commands.cooldown(rate=1, per=3.0, type=commands.BucketType.user)
    @commands.command(name="slots", extras={"example": "slots 500"})
    @commands.guild_only()
    async def slots(self, ctx: commands.Context, amount: WalletAmount) -> None:
        """Spin the slot machine."""
        embed = await econ_views.play_slots(ctx.author.id, amount)
        view = econ_views.RebetView(
            ctx.author.id, amount,
            lambda amt: econ_views.play_slots(ctx.author.id, amt), invoker=ctx.author,
        )
        view.message = await ctx.send(embed=embed, view=view)

    @commands.cooldown(rate=1, per=3.0, type=commands.BucketType.user)
    @commands.command(name="roulette", aliases=["roul"], extras={"example": "roulette 500 red"})
    @commands.guild_only()
    async def roulette(self, ctx: commands.Context, amount: WalletAmount, bet: str) -> None:
        """Bet on roulette: red, black, a dozen (1/2/3), or a number (0-36)."""
        embed = await econ_views.play_roulette(ctx.author.id, amount, bet)
        view = econ_views.RebetView(
            ctx.author.id, amount,
            lambda amt: econ_views.play_roulette(ctx.author.id, amt, bet), invoker=ctx.author,
        )
        view.message = await ctx.send(embed=embed, view=view)

    @commands.cooldown(rate=1, per=3.0, type=commands.BucketType.user)
    @commands.command(name="dice", extras={"example": "dice 500 50"})
    @commands.guild_only()
    async def dice(self, ctx: commands.Context, amount: WalletAmount, target: int) -> None:
        """Roll under your target (2-98). Lower target, higher payout."""
        embed = await econ_views.play_dice(ctx.author.id, amount, target)
        view = econ_views.RebetView(
            ctx.author.id, amount,
            lambda amt: econ_views.play_dice(ctx.author.id, amt, target), invoker=ctx.author,
        )
        view.message = await ctx.send(embed=embed, view=view)

    @commands.cooldown(rate=1, per=3.0, type=commands.BucketType.user)
    @commands.command(name="limbo", extras={"example": "limbo 500 2.5"})
    @commands.guild_only()
    async def limbo(self, ctx: commands.Context, amount: WalletAmount, target: float) -> None:
        """Set a target multiplier. Win if the round reaches it."""
        embed = await econ_views.play_limbo(ctx.author.id, amount, target)
        view = econ_views.RebetView(
            ctx.author.id, amount,
            lambda amt: econ_views.play_limbo(ctx.author.id, amt, target), invoker=ctx.author,
        )
        view.message = await ctx.send(embed=embed, view=view)

    @commands.cooldown(rate=1, per=3.0, type=commands.BucketType.user)
    @commands.command(name="plinko", extras={"example": "plinko 500"})
    @commands.guild_only()
    async def plinko(self, ctx: commands.Context, amount: WalletAmount) -> None:
        """Drop a ball down the pegs into a multiplier bucket."""
        embed = await econ_views.play_plinko(ctx.author.id, amount)
        view = econ_views.RebetView(
            ctx.author.id, amount,
            lambda amt: econ_views.play_plinko(ctx.author.id, amt), invoker=ctx.author,
        )
        view.message = await ctx.send(embed=embed, view=view)

    # ── interactive (multi-step) games ───────────────────────────────────────────

    @commands.cooldown(rate=1, per=3.0, type=commands.BucketType.user)
    @commands.command(name="ladder", extras={"example": "ladder 500"})
    @commands.guild_only()
    async def ladder(self, ctx: commands.Context, amount: WalletAmount) -> None:
        """Climb the ladder for rising multipliers. Cash out before you bust."""
        session_id = await service.escrow_stake(ctx.author.id, amount)
        view = LadderView(ctx.author.id, amount, session_id)
        view.message = await ctx.send(embed=view.embed(), view=view)

    @commands.cooldown(rate=1, per=3.0, type=commands.BucketType.user)
    @commands.command(name="crash", extras={"example": "crash 500"})
    @commands.guild_only()
    async def crash(self, ctx: commands.Context, amount: WalletAmount) -> None:
        """Watch the multiplier climb and cash out before it crashes."""
        session_id = await service.escrow_stake(ctx.author.id, amount)
        view = CrashView(ctx.author.id, amount, session_id)
        view.message = await ctx.send(embed=view.embed(), view=view)

    @commands.cooldown(rate=1, per=3.0, type=commands.BucketType.user)
    @commands.command(name="blackjack", aliases=["bj"], extras={"example": "blackjack 500"})
    @commands.guild_only()
    async def blackjack(self, ctx: commands.Context, amount: WalletAmount) -> None:
        """Play blackjack against the dealer."""
        session_id = await service.escrow_stake(ctx.author.id, amount)
        view = BlackjackView(ctx.author.id, amount, session_id)
        # natural blackjack settles immediately
        if view._game.result() == "natural":
            payout = int(amount * config.BLACKJACK_NATURAL_PAYOUT)
            wallet = await service.payout_winnings(ctx.author.id, payout, session_id)
            for child in view.children:
                child.disabled = True
            e = view.embed(
                reveal_dealer=True,
                status=f"{Emojis.WIN} Natural blackjack! Paid 3:2.\nWallet: {wallet:,}",
            )
            # Mark resolved + stop so on_timeout doesn't log a false forfeit ~90s later.
            view._resolved = True
            view.stop()
            await ctx.send(embed=e, view=view)
            return
        view.message = await ctx.send(embed=view.embed(), view=view)

    @commands.cooldown(rate=1, per=3.0, type=commands.BucketType.user)
    @commands.command(name="hilo", extras={"example": "hilo 500"})
    @commands.guild_only()
    async def hilo(self, ctx: commands.Context, amount: WalletAmount) -> None:
        """Guess higher or lower. Each call climbs the multiplier; cash out before you miss."""
        session_id = await service.escrow_stake(ctx.author.id, amount)
        view = HiLoView(ctx.author.id, amount, session_id)
        view.message = await ctx.send(embed=view.embed(), view=view)

    # ── summaries ─────────────────────────────────────────────────────────────

    @commands.command(name="cooldowns", aliases=["cd"])
    @commands.guild_only()
    async def cooldowns(self, ctx: commands.Context) -> None:
        """Show all your cooldowns at a glance."""
        pairs = await service.get_cooldowns(ctx.author.id)
        lines = [f"{Emojis.CLOCK} **{label}** · {status}" for label, status in pairs]
        await ctx.send(embed=embeds.info("\n".join(lines), "Your Cooldowns"))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Economy(bot))
