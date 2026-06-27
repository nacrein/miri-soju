"""Recurring channel messages: add, list, view, remove, with the dispatch loop."""

from __future__ import annotations

import discord
from discord.ext import commands, tasks

from src.core import embeds
from src.core.timeparse import parse_duration
from src.modules.timer import service

_MIN_INTERVAL = 60  # one minute floor to keep timers from spamming


class TimerCog(commands.Cog, name="Timer"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._loop.start()

    def cog_unload(self) -> None:
        self._loop.cancel()

    @commands.group(name="timer", invoke_without_command=True)
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def timer(self, ctx) -> None:
        """Send a message to a channel on an interval."""
        await ctx.send(embed=embeds.info(
            "`,timer add <channel> <interval> <message>` · `view <channel>` · `remove <channel>` · `list`"
        ))

    @timer.command(name="add")
    @commands.has_permissions(manage_messages=True)
    async def timer_add(self, ctx, channel: discord.TextChannel, interval: str, *, message: str) -> None:
        """Add a timer (one timer per channel)."""
        try:
            delta = parse_duration(interval)
        except ValueError as exc:
            raise commands.BadArgument(str(exc))
        seconds = int(delta.total_seconds())
        if seconds < _MIN_INTERVAL:
            raise commands.BadArgument("Interval must be at least one minute.")
        if await service.for_channel(channel.id) is not None:
            raise commands.BadArgument("That channel already has a timer. Remove it first.")
        await service.add(ctx.guild.id, channel.id, seconds, message)
        await ctx.send(embed=embeds.success(f"Timer set for {channel.mention} every {interval}."))

    @timer.command(name="view")
    @commands.has_permissions(manage_messages=True)
    async def timer_view(self, ctx, channel: discord.TextChannel) -> None:
        """Show a channel's timer."""
        timer = await service.for_channel(channel.id)
        if timer is None:
            raise commands.BadArgument("That channel has no timer.")
        e = embeds.info(timer.message, f"Timer in #{channel.name}")
        e.add_field(name="Interval", value=f"{timer.interval_seconds // 60} min")
        await ctx.send(embed=e)

    @timer.command(name="remove")
    @commands.has_permissions(manage_messages=True)
    async def timer_remove(self, ctx, channel: discord.TextChannel) -> None:
        """Remove a channel's timer."""
        if not await service.remove(channel.id):
            raise commands.BadArgument("That channel has no timer.")
        await ctx.send(embed=embeds.success(f"Removed the timer from {channel.mention}."))

    @timer.command(name="list")
    @commands.has_permissions(manage_messages=True)
    async def timer_list(self, ctx) -> None:
        """List timers in this server."""
        rows = await service.all_for(ctx.guild.id)
        if not rows:
            await ctx.send(embed=embeds.info("No timers set."))
            return
        lines = [f"<#{t.channel_id}> · every {t.interval_seconds // 60} min" for t in rows]
        await ctx.send(embed=embeds.info("\n".join(lines), f"Timers ({len(rows)})"))

    @tasks.loop(seconds=30)
    async def _loop(self) -> None:
        for _id, channel_id, message in await service.due_and_reschedule():
            channel = self.bot.get_channel(channel_id)
            if isinstance(channel, discord.TextChannel):
                try:
                    await channel.send(message, allowed_mentions=discord.AllowedMentions.none())
                except discord.HTTPException:
                    pass

    @_loop.before_loop
    async def _before(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TimerCog(bot))
