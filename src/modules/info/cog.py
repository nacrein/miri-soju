"""Read-only lookups: userinfo, serverinfo, avatar. Open to everyone."""

from __future__ import annotations

import discord
from discord.ext import commands

from src.core import embeds


class Info(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.command(name="userinfo", aliases=["whois", "ui"])
    @commands.guild_only()
    async def userinfo(self, ctx, user: discord.Member | discord.User | None = None) -> None:
        """Show details about a user."""
        target = user or ctx.author
        e = embeds.info("", str(target))
        e.set_thumbnail(url=target.display_avatar.url)
        e.add_field(name="ID", value=str(target.id))
        e.add_field(name="Created", value=discord.utils.format_dt(target.created_at, "R"))
        if isinstance(target, discord.Member):
            joined = (
                discord.utils.format_dt(target.joined_at, "R")
                if target.joined_at else "unknown"
            )
            e.add_field(name="Joined", value=joined)
            roles = [r.mention for r in reversed(target.roles[1:])]
            e.add_field(
                name=f"Roles ({len(roles)})",
                value=(" ".join(roles)[:1000] or "None"),
                inline=False,
            )
        await ctx.send(embed=e)

    @commands.command(name="serverinfo", aliases=["guildinfo", "si"])
    @commands.guild_only()
    async def serverinfo(self, ctx) -> None:
        """Show details about this server."""
        g = ctx.guild
        e = embeds.info("", g.name)
        if g.icon:
            e.set_thumbnail(url=g.icon.url)
        e.add_field(name="ID", value=str(g.id))
        e.add_field(name="Owner", value=f"<@{g.owner_id}>")
        e.add_field(name="Created", value=discord.utils.format_dt(g.created_at, "R"))
        e.add_field(name="Members", value=str(g.member_count))
        e.add_field(name="Channels", value=str(len(g.channels)))
        e.add_field(name="Roles", value=str(len(g.roles)))
        e.add_field(name="Boosts", value=f"{g.premium_subscription_count} (Tier {g.premium_tier})")
        await ctx.send(embed=e)

    @commands.command(name="avatar", aliases=["av", "pfp"])
    @commands.guild_only()
    async def avatar(self, ctx, user: discord.User | None = None) -> None:
        """Show a user's avatar full size."""
        target = user or ctx.author
        e = embeds.info("", f"{target.display_name}'s Avatar")
        e.set_image(url=target.display_avatar.url)
        await ctx.send(embed=e)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Info(bot))
