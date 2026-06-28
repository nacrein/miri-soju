"""Cross-server rankings. One command opens a dropdown menu over the global
boards (net worth, voice time, generators); per-server level ranking is ``,top``
in the leveling module."""

from __future__ import annotations

from discord.ext import commands

from src.modules.leaderboard.views import LeaderboardMenu


class Leaderboard(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.hybrid_command(
        name="leaderboard", aliases=["lb", "rich", "networth", "net", "worth"]
    )
    @commands.guild_only()
    async def leaderboard(self, ctx: commands.Context) -> None:
        """Server-wide rankings. Use the dropdown to switch board."""
        await LeaderboardMenu(ctx.author.id, ctx.guild, ctx.author).start(ctx)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Leaderboard(bot))
