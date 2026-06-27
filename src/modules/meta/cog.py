"""Public bot meta: ping, botinfo, invite. Open to everyone."""

from __future__ import annotations

import time

import discord
from discord.ext import commands

from src.core import embeds
from src.core.emojis import Emojis

# Permissions the invite link requests — the union of what this bot's features need.
_INVITE_PERMS = discord.Permissions(
    manage_roles=True,
    manage_channels=True,
    kick_members=True,
    ban_members=True,
    manage_messages=True,
    manage_nicknames=True,
    moderate_members=True,
    manage_webhooks=True,
    manage_emojis_and_stickers=True,
    view_audit_log=True,
    view_channel=True,
    send_messages=True,
    embed_links=True,
    attach_files=True,
    add_reactions=True,
    use_external_emojis=True,
    read_message_history=True,
)


class Meta(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._start = discord.utils.utcnow()

    @commands.hybrid_command(name="ping")
    async def ping(self, ctx: commands.Context) -> None:
        """Show gateway latency and round-trip time."""
        gateway = self.bot.latency * 1000
        start = time.perf_counter()
        msg = await ctx.send(embed=embeds.info("Pinging..."))
        rtt = (time.perf_counter() - start) * 1000
        await msg.edit(
            embed=embeds.info(f"Gateway: `{gateway:.0f}ms` · Round-trip: `{rtt:.0f}ms`", "Pong")
        )

    @commands.hybrid_command(name="botinfo", aliases=["about"])
    async def botinfo(self, ctx: commands.Context) -> None:
        """Show bot stats: servers, members, uptime, and latency."""
        members = sum(g.member_count or 0 for g in self.bot.guilds)
        command_count = sum(1 for _ in self.bot.walk_commands())
        e = embeds.info("", f"{Emojis.INFO} {self.bot.user.name}")
        e.set_thumbnail(url=self.bot.user.display_avatar.url)
        e.add_field(name="Servers", value=str(len(self.bot.guilds)))
        e.add_field(name="Members", value=f"{members:,}")
        e.add_field(name="Commands", value=str(command_count))
        e.add_field(name="Latency", value=f"{self.bot.latency * 1000:.0f}ms")
        e.add_field(name="Uptime", value=discord.utils.format_dt(self._start, "R"))
        e.add_field(name="Library", value=f"discord.py {discord.__version__}")
        await ctx.send(embed=e)

    @commands.hybrid_command(name="invite")
    async def invite(self, ctx: commands.Context) -> None:
        """Get a link to add me to another server."""
        url = discord.utils.oauth_url(
            self.bot.user.id,
            permissions=_INVITE_PERMS,
            scopes=("bot", "applications.commands"),
        )
        await ctx.send(embed=embeds.info(f"[Click here to invite me]({url})", "Invite"))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Meta(bot))
