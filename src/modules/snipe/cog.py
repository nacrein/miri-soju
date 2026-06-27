"""Snipe: recover the last deleted or edited message in a channel.

State is in-memory and only the most recent message per channel is kept, so it
costs almost nothing and clears on restart.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import discord
from discord.ext import commands

from src.core import embeds
from src.core.emojis import Emojis


@dataclass
class _Deleted:
    author: str
    avatar: str
    content: str
    when: datetime
    attachments: int


@dataclass
class _Edited:
    author: str
    avatar: str
    before: str
    after: str
    when: datetime
    jump_url: str


class Snipe(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._deleted: dict[int, _Deleted] = {}  # channel_id -> last deletion
        self._edited: dict[int, _Edited] = {}     # channel_id -> last edit

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message) -> None:
        if message.guild is None or message.author.bot:
            return
        if not message.content and not message.attachments:
            return
        self._deleted[message.channel.id] = _Deleted(
            author=str(message.author),
            avatar=message.author.display_avatar.url,
            content=message.content,
            when=message.created_at,
            attachments=len(message.attachments),
        )

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:
        if before.guild is None or before.author.bot or before.content == after.content:
            return
        self._edited[before.channel.id] = _Edited(
            author=str(before.author),
            avatar=before.author.display_avatar.url,
            before=before.content,
            after=after.content,
            when=before.created_at,
            jump_url=after.jump_url,
        )

    @commands.command(name="snipe", aliases=["s"])
    @commands.guild_only()
    async def snipe(self, ctx: commands.Context) -> None:
        """Show the last deleted message in this channel."""
        snipe = self._deleted.get(ctx.channel.id)
        if snipe is None:
            await ctx.send(embed=embeds.info("Nothing to snipe here."))
            return
        e = embeds.info(snipe.content or "*(no text)*", f"{Emojis.MESSAGE_DELETE} Deleted message")
        e.set_author(name=snipe.author, icon_url=snipe.avatar)
        if snipe.attachments:
            e.add_field(name="Attachments", value=str(snipe.attachments))
        e.timestamp = snipe.when
        await ctx.send(embed=e)

    @commands.command(name="editsnipe", aliases=["esnipe", "es"])
    @commands.guild_only()
    async def editsnipe(self, ctx: commands.Context) -> None:
        """Show the last edited message in this channel, before and after."""
        snipe = self._edited.get(ctx.channel.id)
        if snipe is None:
            await ctx.send(embed=embeds.info("No recent edits to snipe here."))
            return
        e = embeds.info("", f"{Emojis.MESSAGE_EDIT} Edited message")
        e.set_author(name=snipe.author, icon_url=snipe.avatar)
        e.add_field(name="Before", value=(snipe.before or "—")[:1000], inline=False)
        e.add_field(name="After", value=(snipe.after or "—")[:1000], inline=False)
        e.add_field(name="Jump", value=f"[link]({snipe.jump_url})", inline=False)
        e.timestamp = snipe.when
        await ctx.send(embed=e)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Snipe(bot))
