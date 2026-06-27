"""Read-only lookups: userinfo, serverinfo, avatar. Open to everyone."""

from __future__ import annotations

import discord
from discord.ext import commands

from src.core import embeds
from src.core.emojis import Emojis
from src.core.paginator import Paginator, paginate_lines


class Info(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.hybrid_command(name="userinfo", aliases=["whois", "ui"])
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

    @commands.hybrid_command(name="serverinfo", aliases=["guildinfo", "si"])
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

    @commands.hybrid_command(name="avatar", aliases=["av", "pfp"])
    @commands.guild_only()
    async def avatar(self, ctx, user: discord.User | None = None) -> None:
        """Show a user's avatar full size."""
        target = user or ctx.author
        e = embeds.info("", f"{target.display_name}'s Avatar")
        e.set_image(url=target.display_avatar.url)
        await ctx.send(embed=e)

    @commands.hybrid_command(name="banner")
    @commands.guild_only()
    async def banner(self, ctx, user: discord.User | None = None) -> None:
        """Show a user's profile banner."""
        target = user or ctx.author
        fetched = await self.bot.fetch_user(target.id)  # banner isn't on cached users
        if fetched.banner is None:
            await ctx.send(embed=embeds.info(f"{target.display_name} has no banner."))
            return
        e = embeds.info("", f"{target.display_name}'s Banner")
        e.set_image(url=fetched.banner.url)
        await ctx.send(embed=e)

    @commands.hybrid_command(name="membercount", aliases=["members", "mc"])
    @commands.guild_only()
    async def membercount(self, ctx) -> None:
        """Show how many members are in this server."""
        g = ctx.guild
        humans = sum(1 for m in g.members if not m.bot)
        bots = (g.member_count or 0) - humans
        e = embeds.info("", f"{g.name} — Members")
        e.add_field(name="Total", value=str(g.member_count))
        e.add_field(name="Humans", value=str(humans))
        e.add_field(name="Bots", value=str(bots))
        await ctx.send(embed=e)

    @commands.hybrid_command(name="roles")
    @commands.guild_only()
    async def roles(self, ctx) -> None:
        """List every role in this server, highest first."""
        roles = [r for r in reversed(ctx.guild.roles) if not r.is_default()]
        if not roles:
            await ctx.send(embed=embeds.info("This server has no roles."))
            return
        lines = [f"{r.mention} — {len(r.members)} member(s)" for r in roles]
        pages = paginate_lines(lines, f"{Emojis.ROLE} Roles ({len(roles)})")
        await Paginator(ctx.author.id, pages).start(ctx)

    @commands.hybrid_command(name="inrole", extras={"example": "inrole Moderator"})
    @commands.guild_only()
    async def inrole(self, ctx, *, role: discord.Role) -> None:
        """List the members who have a role."""
        members = role.members
        if not members:
            await ctx.send(embed=embeds.info(f"No members have {role.mention}."))
            return
        lines = [f"{m.mention} (`{m}`)" for m in members]
        pages = paginate_lines(lines, f"{role.name} — {len(members)} member(s)")
        await Paginator(ctx.author.id, pages).start(ctx)

    @commands.command(name="channelinfo", aliases=["ci"])
    @commands.guild_only()
    async def channelinfo(self, ctx, channel: discord.abc.GuildChannel | None = None) -> None:
        """Show details about a channel (defaults to this one)."""
        ch = channel or ctx.channel
        e = embeds.info("", f"{Emojis.CHANNEL} {ch.name}")
        e.add_field(name="ID", value=str(ch.id))
        e.add_field(name="Type", value=str(ch.type))
        e.add_field(name="Created", value=discord.utils.format_dt(ch.created_at, "R"))
        e.add_field(name="Category", value=ch.category.name if ch.category else "—")
        topic = getattr(ch, "topic", None)
        if topic:
            e.add_field(name="Topic", value=topic[:1000], inline=False)
        await ctx.send(embed=e)

    @commands.command(name="emojiinfo", aliases=["ei"])
    @commands.guild_only()
    async def emojiinfo(self, ctx, emoji: discord.PartialEmoji) -> None:
        """Show details about a custom emoji."""
        if emoji.id is None:
            await ctx.send(embed=embeds.info("That's a default emoji, not a custom one."))
            return
        e = embeds.info("", emoji.name)
        e.set_thumbnail(url=emoji.url)
        e.add_field(name="ID", value=str(emoji.id))
        e.add_field(name="Animated", value="Yes" if emoji.animated else "No")
        e.add_field(name="Created", value=discord.utils.format_dt(emoji.created_at, "R"))
        e.add_field(name="Usage", value=f"`{emoji}`", inline=False)
        await ctx.send(embed=e)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Info(bot))
