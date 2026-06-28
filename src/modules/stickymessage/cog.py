"""Sticky messages: add, remove, list, view, plus the repost listener."""

from __future__ import annotations

import time

import discord
from discord.ext import commands

from src.core import embeds
from src.core.emojis import Emojis
from src.core.paginator import send_command_browser
from src.modules.stickymessage import service

_REPOST_COOLDOWN = 5.0  # seconds; avoids hammering a busy channel


class StickyMessageCog(commands.Cog, name="StickyMessage"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._last_repost: dict[int, float] = {}

    @commands.group(name="stickymessage", aliases=["sticky"], invoke_without_command=True)
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def stickymessage(self, ctx) -> None:
        """A message pinned to the bottom of a channel by reposting."""
        await send_command_browser(ctx, ctx.command)

    @stickymessage.command(name="add")
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def sticky_add(self, ctx, channel: discord.TextChannel, *, content: str) -> None:
        """Set the sticky message for a channel."""
        await service.set_sticky(channel.id, ctx.guild.id, content)
        await ctx.send(embed=embeds.success(f"Sticky message set for {channel.mention}."))

    @stickymessage.command(name="remove")
    @commands.has_permissions(manage_messages=True)
    async def sticky_remove(self, ctx, channel: discord.TextChannel) -> None:
        """Remove a channel's sticky message."""
        if not await service.remove(channel.id):
            raise commands.BadArgument("That channel has no sticky message.")
        await ctx.send(embed=embeds.success(f"Removed the sticky message from {channel.mention}."))

    @stickymessage.command(name="view")
    @commands.has_permissions(manage_messages=True)
    async def sticky_view(self, ctx, channel: discord.TextChannel) -> None:
        """Show a channel's sticky message content."""
        row = await service.get_sticky(channel.id)
        if row is None:
            raise commands.BadArgument("That channel has no sticky message.")
        await ctx.send(embed=embeds.info(row.content, f"Sticky in #{channel.name}"))

    @stickymessage.command(name="list")
    @commands.has_permissions(manage_messages=True)
    async def sticky_list(self, ctx) -> None:
        """List channels with sticky messages."""
        rows = await service.all_for(ctx.guild.id)
        if not rows:
            await ctx.send(embed=embeds.info("No sticky messages set."))
            return
        await ctx.send(embed=embeds.info("\n".join(f"<#{r.channel_id}>" for r in rows), f"Sticky Messages ({len(rows)})"))

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or message.guild is None:
            return
        row = await service.get_sticky(message.channel.id)
        if row is None:
            return
        now = time.monotonic()
        if now - self._last_repost.get(message.channel.id, 0.0) < _REPOST_COOLDOWN:
            return
        self._last_repost[message.channel.id] = now
        if row.last_message_id:
            try:
                old = await message.channel.fetch_message(row.last_message_id)
                await old.delete()
            except discord.HTTPException:
                pass
        try:
            sent = await message.channel.send(embed=embeds.info(row.content, f"{Emojis.PIN} Sticky"))
            await service.set_last(message.channel.id, sent.id)
        except discord.HTTPException:
            pass


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(StickyMessageCog(bot))
