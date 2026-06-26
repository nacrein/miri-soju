"""Economy commands: wallet, daily, work, pray, give, deposit, withdraw."""

from __future__ import annotations

import discord
from discord.ext import commands

from src.core import embeds
from src.core.emojis import Emojis
from src.modules.economy import config, service
from src.modules.economy.games.views import BlackjackView, CrashView, HiLoView, LadderView


def _fmt(n: int) -> str:
    return f"{n:,}"


class Economy(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.hybrid_command(name="wallet", extras={"example": "wallet @user"})
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

    @commands.command(name="work")
    @commands.guild_only()
    async def work(self, ctx: commands.Context) -> None:
        """Work for some bits."""
        amount = await service.work(ctx.author.id)
        await ctx.send(embed=embeds.success(f"You earned {Emojis.BITS} **{_fmt(amount)}** working."))

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

    @commands.command(name="give", extras={"example": "give @user 500"})
    @commands.guild_only()
    async def give(self, ctx: commands.Context, user: discord.User, amount: int) -> None:
        """Give bits from your wallet to another player."""
        await service.give(ctx.author.id, user.id, amount)
        await ctx.send(
            embed=embeds.success(f"You gave {Emojis.BITS} **{_fmt(amount)}** to {user.mention}.")
        )

    @commands.command(name="deposit", aliases=["dep"], extras={"example": "deposit 1000"})
    @commands.guild_only()
    async def deposit(self, ctx: commands.Context, amount: int) -> None:
        """Move bits from your wallet into your safe vault."""
        moved = await service.deposit(ctx.author.id, amount)
        await ctx.send(
            embed=embeds.success(f"Deposited {Emojis.BANK} **{_fmt(moved)}** into your vault.")
        )

    @commands.command(name="withdraw", aliases=["with"], extras={"example": "withdraw 1000"})
    @commands.guild_only()
    async def withdraw(self, ctx: commands.Context, amount: int) -> None:
        """Move bits from your vault back into your wallet."""
        moved = await service.withdraw(ctx.author.id, amount)
        await ctx.send(
            embed=embeds.success(f"Withdrew {Emojis.BITS} **{_fmt(moved)}** to your wallet.")
        )


    # ── vault upgrades ──────────────────────────────────────────────────────

    @commands.group(name="vault")
    @commands.guild_only()
    async def vault(self, ctx: commands.Context) -> None:
        """View your vault and upgrade its capacity."""
        if ctx.invoked_subcommand is None:
            w, v, cap = await service.get_balance(ctx.author.id)
            info = service.vault_upgrade_info(cap)
            e = embeds.info("", f"{Emojis.BANK} Your Vault")
            e.add_field(name="Stored", value=f"{_fmt(v)} / {_fmt(cap)}", inline=False)
            if info is None:
                e.add_field(name="Upgrade", value="Maxed out.", inline=False)
            else:
                next_cap, cost = info
                e.add_field(
                    name="Next upgrade",
                    value=f"Capacity {_fmt(next_cap)} for {Emojis.BITS} {_fmt(cost)}\n"
                          f"Use `,vault upgrade`",
                    inline=False,
                )
            await ctx.send(embed=e)

    @vault.command(name="upgrade")
    async def vault_upgrade(self, ctx: commands.Context) -> None:
        """Buy the next vault capacity tier (paid from your wallet)."""
        new_cap, cost = await service.upgrade_vault(ctx.author.id)
        await ctx.send(
            embed=embeds.success(
                f"Vault upgraded to {Emojis.BANK} **{_fmt(new_cap)}** capacity "
                f"for {Emojis.BITS} {_fmt(cost)}."
            )
        )

    # ── generator ───────────────────────────────────────────────────────────

    @commands.group(name="generator", aliases=["gen"])
    @commands.guild_only()
    async def generator(self, ctx: commands.Context) -> None:
        """View, claim, and upgrade your passive bit generator."""
        if ctx.invoked_subcommand is None:
            tier, rate, pending = await service.get_generator(ctx.author.id)
            e = embeds.info("", f"{Emojis.SETTINGS} Your Generator")
            if tier <= 0:
                e.description = "You don't own a generator yet."
                up = service.generator_upgrade_info(0)
                if up:
                    nt, nr, cost = up
                    e.add_field(
                        name="Buy one",
                        value=f"Tier {nt}: {_fmt(nr)}/hr for {Emojis.BITS} {_fmt(cost)}\n"
                              f"Use `,generator upgrade`",
                        inline=False,
                    )
            else:
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
                e.set_footer(text="Use ,generator claim  ·  ,generator upgrade")
            await ctx.send(embed=e)

    @generator.command(name="claim")
    async def generator_claim(self, ctx: commands.Context) -> None:
        """Collect the bits your generator has produced."""
        amount = await service.claim_generator(ctx.author.id)
        await ctx.send(
            embed=embeds.success(f"Collected {Emojis.BITS} **{_fmt(amount)}** from your generator.")
        )

    @generator.command(name="upgrade")
    async def generator_upgrade(self, ctx: commands.Context) -> None:
        """Buy the next generator tier (auto-collects pending bits first)."""
        new_tier, new_rate, cost = await service.upgrade_generator(ctx.author.id)
        await ctx.send(
            embed=embeds.success(
                f"Generator upgraded to **tier {new_tier}** ({_fmt(new_rate)}/hr) "
                f"for {Emojis.BITS} {_fmt(cost)}."
            )
        )


    # ── steal ───────────────────────────────────────────────────────────────

    @commands.command(name="steal", extras={"example": "steal @user"})
    @commands.guild_only()
    async def steal(self, ctx: commands.Context, user: discord.User) -> None:
        """Attempt to steal bits from someone's wallet. Risky."""
        success, delta = await service.steal(ctx.author.id, user.id)
        if success:
            await ctx.send(embed=embeds.success(
                f"{Emojis.WIN} You stole {Emojis.BITS} **{_fmt(delta)}** from {user.mention}!"
            ))
        else:
            await ctx.send(embed=embeds.error(
                f"You got caught and paid a fine of {Emojis.BITS} **{_fmt(-delta)}**."
            ))

    # ── gambling ────────────────────────────────────────────────────────────

    @commands.cooldown(rate=1, per=3.0, type=commands.BucketType.user)
    @commands.command(name="coinflip", aliases=["cf"], extras={"example": "coinflip 500 heads"})
    @commands.guild_only()
    async def coinflip(self, ctx: commands.Context, amount: int, call: str) -> None:
        """Bet on a coin flip. Call heads or tails."""
        won, result, net, wallet = await service.coinflip(ctx.author.id, amount, call)
        verb = "won" if won else "lost"
        e = (embeds.success if won else embeds.error)(
            f"{Emojis.COIN_FLIP} It landed **{result}**. You {verb} "
            f"{Emojis.BITS} **{_fmt(abs(net))}**.\nWallet: {_fmt(wallet)}"
        )
        await ctx.send(embed=e)

    @commands.cooldown(rate=1, per=3.0, type=commands.BucketType.user)
    @commands.command(name="slots", extras={"example": "slots 500"})
    @commands.guild_only()
    async def slots(self, ctx: commands.Context, amount: int) -> None:
        """Spin the slot machine."""
        reels, net, wallet = await service.slots(ctx.author.id, amount)
        won = net > 0
        line = " ".join(reels)
        e = (embeds.success if won else embeds.error)(
            f"{Emojis.SLOTS} [ {line} ]\n"
            + (f"You won {Emojis.BITS} **{_fmt(net)}**!" if won
               else f"You lost {Emojis.BITS} **{_fmt(amount)}**.")
            + f"\nWallet: {_fmt(wallet)}"
        )
        await ctx.send(embed=e)

    @commands.cooldown(rate=1, per=3.0, type=commands.BucketType.user)
    @commands.command(name="roulette", aliases=["roul"], extras={"example": "roulette 500 red"})
    @commands.guild_only()
    async def roulette(self, ctx: commands.Context, amount: int, bet: str) -> None:
        """Bet on roulette: red, black, a dozen (1/2/3), or a number (0-36)."""
        result, color, net, wallet = await service.roulette(ctx.author.id, amount, bet)
        won = net > 0
        e = (embeds.success if won else embeds.error)(
            f"{Emojis.DICE} The ball landed on **{result}** ({color}).\n"
            + (f"You won {Emojis.BITS} **{_fmt(net)}**!" if won
               else f"You lost {Emojis.BITS} **{_fmt(amount)}**.")
            + f"\nWallet: {_fmt(wallet)}"
        )
        await ctx.send(embed=e)

    @commands.cooldown(rate=1, per=3.0, type=commands.BucketType.user)
    @commands.command(name="dice", extras={"example": "dice 500 50"})
    @commands.guild_only()
    async def dice(self, ctx: commands.Context, amount: int, target: int) -> None:
        """Roll under your target (2-98). Lower target, higher payout."""
        won, roll, target, net, wallet = await service.dice(ctx.author.id, amount, target)
        e = (embeds.success if won else embeds.error)(
            f"{Emojis.DICE} Rolled **{roll}** vs target **{target}**.\n"
            + (f"You won {Emojis.BITS} **{_fmt(net)}**!" if won
               else f"You lost {Emojis.BITS} **{_fmt(amount)}**.")
            + f"\nWallet: {_fmt(wallet)}"
        )
        await ctx.send(embed=e)

    @commands.cooldown(rate=1, per=3.0, type=commands.BucketType.user)
    @commands.command(name="limbo", extras={"example": "limbo 500 2.5"})
    @commands.guild_only()
    async def limbo(self, ctx: commands.Context, amount: int, target: float) -> None:
        """Set a target multiplier. Win if the round reaches it."""
        won, outcome, target, net, wallet = await service.limbo(ctx.author.id, amount, target)
        e = (embeds.success if won else embeds.error)(
            f"{Emojis.DICE} Round hit **{outcome:.2f}x** (target **{target:.2f}x**).\n"
            + (f"You won {Emojis.BITS} **{_fmt(net)}**!" if won
               else f"You lost {Emojis.BITS} **{_fmt(amount)}**.")
            + f"\nWallet: {_fmt(wallet)}"
        )
        await ctx.send(embed=e)

    @commands.cooldown(rate=1, per=3.0, type=commands.BucketType.user)
    @commands.command(name="plinko", extras={"example": "plinko 500"})
    @commands.guild_only()
    async def plinko(self, ctx: commands.Context, amount: int) -> None:
        """Drop a ball down the pegs into a multiplier bucket."""
        bucket, path, mult, net, wallet = await service.plinko(ctx.author.id, amount)
        won = net > 0
        row = " ".join(
            f"[{m:g}]" if i == bucket else f"{m:g}"
            for i, m in enumerate(config.PLINKO_MULTIPLIERS)
        )
        e = (embeds.success if won else embeds.error)(
            f"{Emojis.SLOTS} {row}\n"
            f"Path: {' '.join(path)} → **{mult:.2f}x**\n"
            + (f"You won {Emojis.BITS} **{_fmt(net)}**!" if won
               else f"You lost {Emojis.BITS} **{_fmt(amount)}**.")
            + f"\nWallet: {_fmt(wallet)}"
        )
        await ctx.send(embed=e)

    # ── leaderboard ─────────────────────────────────────────────────────────

    @commands.command(name="leaderboard", aliases=["lb", "rich"])
    @commands.guild_only()
    async def leaderboard(self, ctx: commands.Context) -> None:
        """Show the richest players by net worth."""
        rows = await service.leaderboard(10)
        if not rows:
            await ctx.send(embed=embeds.info("No players yet."))
            return
        lines = []
        for i, (uid, worth) in enumerate(rows, 1):
            member = ctx.guild.get_member(uid)
            name = member.display_name if member else f"User {uid}"
            medal = {1: Emojis.TROPHY, 2: Emojis.MEDAL_SILVER, 3: Emojis.MEDAL_BRONZE}.get(i, f"`{i}.`")
            lines.append(f"{medal} **{name}** — {Emojis.BITS} {_fmt(worth)}")
        await ctx.send(embed=embeds.info("\n".join(lines), f"{Emojis.TROPHY} Richest Players"))


    # ── interactive games ───────────────────────────────────────────────────

    @commands.cooldown(rate=1, per=3.0, type=commands.BucketType.user)
    @commands.command(name="ladder", extras={"example": "ladder 500"})
    @commands.guild_only()
    async def ladder(self, ctx: commands.Context, amount: int) -> None:
        """Climb the ladder for rising multipliers. Cash out before you bust."""
        session_id = await service.escrow_stake(ctx.author.id, amount)
        view = LadderView(ctx.author.id, amount, session_id)
        view.message = await ctx.send(embed=view.embed(), view=view)

    @commands.cooldown(rate=1, per=3.0, type=commands.BucketType.user)
    @commands.command(name="crash", extras={"example": "crash 500"})
    @commands.guild_only()
    async def crash(self, ctx: commands.Context, amount: int) -> None:
        """Watch the multiplier climb and cash out before it crashes."""
        session_id = await service.escrow_stake(ctx.author.id, amount)
        view = CrashView(ctx.author.id, amount, session_id)
        view.message = await ctx.send(embed=view.embed(), view=view)

    @commands.cooldown(rate=1, per=3.0, type=commands.BucketType.user)
    @commands.command(name="blackjack", aliases=["bj"], extras={"example": "blackjack 500"})
    @commands.guild_only()
    async def blackjack(self, ctx: commands.Context, amount: int) -> None:
        """Play blackjack against the dealer."""
        session_id = await service.escrow_stake(ctx.author.id, amount)
        view = BlackjackView(ctx.author.id, amount, session_id)
        # natural blackjack settles immediately
        if view._game.result() == "natural":
            payout = int(amount * config.BLACKJACK_NATURAL_PAYOUT)
            wallet = await service.payout_winnings(ctx.author.id, payout, session_id)
            for child in view.children:
                child.disabled = True
            e = view.embed(reveal_dealer=True, status=f"{Emojis.WIN} Natural blackjack! Paid 3:2.\nWallet: {wallet:,}")
            # Mark resolved + stop so on_timeout doesn't log a false forfeit ~90s later.
            view._resolved = True
            view.stop()
            await ctx.send(embed=e, view=view)
            return
        view.message = await ctx.send(embed=view.embed(), view=view)

    @commands.cooldown(rate=1, per=3.0, type=commands.BucketType.user)
    @commands.command(name="hilo", extras={"example": "hilo 500"})
    @commands.guild_only()
    async def hilo(self, ctx: commands.Context, amount: int) -> None:
        """Guess higher or lower. Each call climbs the multiplier; cash out before you miss."""
        session_id = await service.escrow_stake(ctx.author.id, amount)
        view = HiLoView(ctx.author.id, amount, session_id)
        view.message = await ctx.send(embed=view.embed(), view=view)


    # ── summaries ───────────────────────────────────────────────────────────

    @commands.command(name="cooldowns", aliases=["cd"])
    @commands.guild_only()
    async def cooldowns(self, ctx: commands.Context) -> None:
        """Show all your cooldowns at a glance."""
        pairs = await service.get_cooldowns(ctx.author.id)
        lines = [f"{Emojis.CLOCK} **{label}** — {status}" for label, status in pairs]
        await ctx.send(embed=embeds.info("\n".join(lines), "Your Cooldowns"))

    @commands.command(name="stats")
    @commands.guild_only()
    async def stats(self, ctx: commands.Context) -> None:
        """Show your economy stats."""
        s = await service.get_stats(ctx.author.id)
        rank = f"#{s['rank']}" if s["rank"] else "—"
        e = embeds.info("", f"{Emojis.RANK} {ctx.author.display_name}'s Stats")
        e.add_field(name="Net Worth", value=f"{Emojis.BITS} {_fmt(s['net_worth'])}")
        e.add_field(name="Rank", value=rank)
        e.add_field(name="Daily Streak", value=f"{Emojis.FIRE} {s['daily_streak']}")
        e.add_field(name="Wallet", value=f"{Emojis.BITS} {_fmt(s['wallet'])}")
        e.add_field(name="Vault", value=f"{Emojis.BANK} {_fmt(s['vault'])} / {_fmt(s['vault_capacity'])}")
        if s["generator_tier"] > 0:
            e.add_field(name="Generator", value=f"T{s['generator_tier']} · {_fmt(s['generator_rate'])}/hr")
        await ctx.send(embed=e)

    @commands.command(name="profile", aliases=["p"])
    @commands.guild_only()
    async def profile(self, ctx: commands.Context, user: discord.User | None = None) -> None:
        """Your full economy card: balances, rank, streak, generator, cooldowns."""
        target = user or ctx.author
        p = await service.get_profile(target.id)
        rank = f"#{p['rank']}" if p["rank"] else "—"
        e = embeds.info("", f"{Emojis.RANK} {target.display_name}'s Profile")
        e.add_field(name="Net Worth", value=f"{Emojis.BITS} {_fmt(p['net_worth'])}")
        e.add_field(name="Rank", value=rank)
        e.add_field(name="Daily Streak", value=f"{Emojis.FIRE} {p['daily_streak']}")
        e.add_field(name="Wallet", value=f"{Emojis.BITS} {_fmt(p['wallet'])}")
        vault = f"{Emojis.BANK} {_fmt(p['vault'])} / {_fmt(p['vault_capacity'])}"
        e.add_field(name="Vault", value=vault)
        if p["generator_tier"] > 0:
            e.add_field(
                name="Generator",
                value=f"T{p['generator_tier']} · {_fmt(p['generator_rate'])}/hr "
                      f"(+{_fmt(p['generator_pending'])} pending)",
            )
        cd = " · ".join(f"{label}: {status}" for label, status in p["cooldowns"])
        e.add_field(name="Cooldowns", value=cd, inline=False)
        await ctx.send(embed=e)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Economy(bot))
