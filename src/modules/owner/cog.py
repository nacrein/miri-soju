"""Owner-only bot conveniences. Locked to the bot owner.

Eval, shell, reload, sync, and impersonate are provided by jishaku (`jsk ...`).
This cog holds the bot-specific quality-of-life commands jishaku doesn't.
"""

from __future__ import annotations

import logging

import discord
from discord.ext import commands

from src.core import embeds
from src.core.emojis import Emojis
from src.core.paginator import Paginator, paginate_lines

log = logging.getLogger(__name__)


class Owner(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_check(self, ctx: commands.Context) -> bool:
        return await self.bot.is_owner(ctx.author)

    @commands.command(name="status")
    async def status(self, ctx: commands.Context) -> None:
        """Show bot stats: servers, users, latency, loaded cogs."""
        e = embeds.info("", f"{Emojis.SETTINGS} Status")
        e.add_field(name=f"{Emojis.CHANNEL} Servers", value=str(len(self.bot.guilds)))
        e.add_field(name=f"{Emojis.JOIN} Users", value=str(len(self.bot.users)))
        e.add_field(name=f"{Emojis.ONLINE} Latency", value=f"{self.bot.latency * 1000:.0f}ms")
        e.add_field(name=f"{Emojis.SETTINGS} Cogs", value=str(len(self.bot.cogs)))
        await ctx.send(embed=e)

    @commands.command(name="servers")
    async def servers(self, ctx: commands.Context) -> None:
        """List servers the bot is in."""
        if not self.bot.guilds:
            await ctx.send(embed=embeds.info("Not in any servers."))
            return
        lines = [
            f"`{g.id}` · **{g.name}** ({g.member_count} members, owner: {g.owner_id})"
            for g in sorted(self.bot.guilds, key=lambda g: g.member_count or 0, reverse=True)
        ]
        pages = paginate_lines(lines, f"Servers ({len(self.bot.guilds)})")
        await Paginator(ctx.author.id, pages).start(ctx)

    @commands.command(name="leaveserver")
    async def leaveserver(self, ctx: commands.Context, guild_id: int) -> None:
        """Make the bot leave a server by id (asks for confirmation)."""
        guild = self.bot.get_guild(guild_id)
        if guild is None:
            await ctx.send(embed=embeds.error("I'm not in a server with that id."))
            return
        prompt = await ctx.send(
            embed=embeds.warning(f"Leave **{guild.name}** (`{guild.id}`)? Reply `yes` to confirm.")
        )

        def check(m: discord.Message) -> bool:
            return (
                m.author == ctx.author
                and m.channel == ctx.channel
                and m.content.lower() == "yes"
            )

        try:
            await self.bot.wait_for("message", check=check, timeout=30)
        except TimeoutError:
            await prompt.edit(embed=embeds.info("Cancelled."))
            return
        await guild.leave()
        await ctx.send(embed=embeds.success(f"{Emojis.LEAVE} Left **{guild.name}**."))
        log.info("Left guild %s (%s) by owner request", guild.name, guild.id)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Owner(bot))
