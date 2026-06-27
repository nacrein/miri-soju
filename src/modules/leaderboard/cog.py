"""Cross-domain rankings. Owns the leaderboard group; each domain feeds it data."""

from __future__ import annotations

import discord
from discord.ext import commands

from src.core import embeds
from src.core.emojis import Emojis
from src.modules.economy import service as economy


def _fmt(n: int) -> str:
    return f"{n:,}"


class Leaderboard(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_check(self, ctx: commands.Context) -> bool:
        """Every board resolves member names off ctx.guild, so all of them are
        guild-only. The group declares guild_only, but with invoke_without_command
        the group's checks are skipped for subcommands (discord.py dispatches
        straight to the subcommand) — a cog_check covers the group and every
        subcommand uniformly, including the leveling ones added later."""
        return ctx.guild is not None

    async def _show_board(self, ctx: commands.Context, entries, title: str) -> None:
        if not entries:
            await ctx.send(embed=embeds.info("No players yet."))
            return
        lines = []
        for i, (uid, value_str) in enumerate(entries, 1):
            member = ctx.guild.get_member(uid)
            name = member.display_name if member else f"User {uid}"
            rank = Emojis.TROPHY if i == 1 else f"`#{i}`"
            lines.append(f"{rank} **{name}** — {value_str}")
        e = embeds.info("\n".join(lines), f"{Emojis.TROPHY} {title}")
        e.set_footer(text="Boards: ,lb networth · ,lb bits · ,lb generator")
        await ctx.send(embed=e)

    @commands.hybrid_group(
        name="leaderboard", aliases=["lb", "top", "rich"], invoke_without_command=True
    )
    @commands.guild_only()
    async def leaderboard(self, ctx: commands.Context) -> None:
        """Server rankings. Bare command shows net worth; subcommands switch the board."""
        rows = await economy.leaderboard(10)
        await self._show_board(ctx, [(uid, f"{Emojis.BITS} {_fmt(w)}") for uid, w in rows], "Net Worth")

    @leaderboard.command(name="networth", aliases=["net", "worth"])
    async def lb_networth(self, ctx: commands.Context) -> None:
        """Top players by wallet plus vault."""
        rows = await economy.leaderboard(10)
        await self._show_board(ctx, [(uid, f"{Emojis.BITS} {_fmt(w)}") for uid, w in rows], "Net Worth")

    @leaderboard.command(name="bits", aliases=["wallet"])
    async def lb_bits(self, ctx: commands.Context) -> None:
        """Top players by liquid wallet bits."""
        rows = await economy.leaderboard_wallet(10)
        await self._show_board(ctx, [(uid, f"{Emojis.BITS} {_fmt(w)}") for uid, w in rows], "Wallet Bits")

    @leaderboard.command(name="generator", aliases=["gen"])
    async def lb_generator(self, ctx: commands.Context) -> None:
        """Top players by generator tier."""
        rows = await economy.leaderboard_generator(10)
        await self._show_board(
            ctx, [(uid, f"T{tier} · {_fmt(rate)}/hr") for uid, tier, rate in rows], "Generators"
        )

    @leaderboard.command(name="level", aliases=["lvl", "xp"])
    async def lb_level(self, ctx: commands.Context) -> None:
        """Top members by level."""
        from src.modules.leveling import service as leveling
        rows = await leveling.leaderboard_level(ctx.guild.id, 10)
        await self._show_board(ctx, [(uid, f"Level {lvl}") for uid, lvl in rows], "Levels")

    @leaderboard.command(name="voice", aliases=["vc"])
    async def lb_voice(self, ctx: commands.Context) -> None:
        """Top members by voice time."""
        from src.modules.leveling import service as leveling
        rows = await leveling.leaderboard_voice(ctx.guild.id, 10)
        await self._show_board(ctx, [(uid, hrs) for uid, hrs in rows], "Voice Time")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Leaderboard(bot))
