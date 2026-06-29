"""Public bot meta: ping, botinfo, invite. Open to everyone."""

from __future__ import annotations

import time

import discord
from discord.ext import commands

from src.core import embeds

# Links shown as buttons on ,botinfo. Leave a value blank to omit its button
# (Discord rejects empty-url buttons, so a blank link simply doesn't appear).
SUPPORT_URL = ""
WEBSITE_URL = ""

# Permissions the invite link requests: the union of what this bot's features need.
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


class _LinkButtons(discord.ui.View):
    """Plain link buttons for ,botinfo: Invite on its own row, then Support and
    Website. Link buttons never fire interactions, so the view needs no timeout
    and a configured-but-blank link is just left off."""

    def __init__(self, invite_url: str, support_url: str, website_url: str) -> None:
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(
            style=discord.ButtonStyle.link, label="Invite", url=invite_url, row=0,
        ))
        if support_url:
            self.add_item(discord.ui.Button(
                style=discord.ButtonStyle.link, label="Support", url=support_url, row=1,
            ))
        if website_url:
            self.add_item(discord.ui.Button(
                style=discord.ButtonStyle.link, label="Website", url=website_url, row=1,
            ))


class Meta(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    def _invite_url(self) -> str:
        """The OAuth invite link requesting this bot's permissions."""
        return discord.utils.oauth_url(
            self.bot.user.id,
            permissions=_INVITE_PERMS,
            scopes=("bot", "applications.commands"),
        )

    @commands.hybrid_command(name="ping")
    async def ping(self, ctx: commands.Context) -> None:
        """Show gateway latency and round-trip time."""
        gateway = self.bot.latency * 1000
        start = time.perf_counter()
        msg = await ctx.send(embed=embeds.info("Pinging..."))
        rtt = (time.perf_counter() - start) * 1000
        # This is a msg.edit (not ctx.send), so the author row is set explicitly.
        await msg.edit(
            embed=embeds.info(
                f"> Gateway `{gateway:.0f}ms` · Round-trip `{rtt:.0f}ms`",
                "Pong",
                author=ctx.author,
            )
        )

    @commands.hybrid_command(name="botinfo", aliases=["about"])
    async def botinfo(self, ctx: commands.Context) -> None:
        """Show bot stats: commands, servers, and users."""
        members = sum(g.member_count or 0 for g in self.bot.guilds)
        command_count = sum(1 for _ in self.bot.walk_commands())
        e = discord.Embed(
            title=self.bot.user.name,
            description=(
                f"Commands: `{command_count}`\n"
                f"Servers: `{len(self.bot.guilds)}`\n"
                f"Users: `{members:,}`"
            ),
            color=embeds.COLOR_SIGNATURE,
        )
        view = _LinkButtons(self._invite_url(), SUPPORT_URL, WEBSITE_URL)
        await ctx.send(embed=e, view=view)

    @commands.hybrid_command(name="invite")
    async def invite(self, ctx: commands.Context) -> None:
        """Get a link to add me to another server."""
        await ctx.send(
            embed=embeds.info(f"> [Click here to invite me]({self._invite_url()})", "Invite")
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Meta(bot))
