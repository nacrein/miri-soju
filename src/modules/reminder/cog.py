"""Personal reminders: add, list, remove, with the delivery loop."""

from __future__ import annotations

from datetime import UTC, datetime

import discord
from discord.ext import commands, tasks

from src.core import embeds
from src.core.paginator import send_command_browser
from src.core.timeparse import parse_duration
from src.modules.reminder import service


class ReminderCog(commands.Cog, name="Reminder"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._loop.start()

    def cog_unload(self) -> None:
        self._loop.cancel()

    @commands.command(name="remind", aliases=["remindme"])
    @commands.guild_only()
    async def remind(self, ctx, duration: str, *, message: str) -> None:
        """Remind yourself after a duration, e.g. `,remind 2h check the oven`."""
        try:
            delta = parse_duration(duration)
        except ValueError as exc:
            raise commands.BadArgument(str(exc)) from exc
        remind_at = datetime.now(UTC) + delta
        await service.add(ctx.author.id, ctx.channel.id, ctx.guild.id, remind_at, message)
        await ctx.send(embed=embeds.success(f"I'll remind you {discord.utils.format_dt(remind_at, 'R')}."))

    @commands.group(name="reminder", invoke_without_command=True)
    @commands.guild_only()
    async def reminder(self, ctx) -> None:
        """Your reminders."""
        await send_command_browser(ctx, ctx.command)

    @reminder.command(name="list")
    async def reminder_list(self, ctx) -> None:
        """List your reminders."""
        rows = await service.for_user(ctx.author.id)
        if not rows:
            await ctx.send(embed=embeds.info("You have no reminders."))
            return
        lines = [
            f"`#{i}` {r.message[:80]} · {discord.utils.format_dt(r.remind_at, 'R')}"
            for i, r in enumerate(rows, 1)
        ]
        await ctx.send(embed=embeds.info("\n".join(lines), f"Your Reminders ({len(rows)})"))

    @reminder.command(name="remove", aliases=["del"])
    async def reminder_remove(self, ctx, index: int) -> None:
        """Remove a reminder by its index."""
        rows = await service.for_user(ctx.author.id)
        if index < 1 or index > len(rows):
            raise commands.BadArgument("No reminder at that index.")
        # The list and the delete run in separate sessions; the row may have
        # fired (or been removed) in between, so trust the delete's rowcount.
        if not await service.remove(ctx.author.id, rows[index - 1].id):
            raise commands.BadArgument("No reminder at that index.")
        await ctx.send(embed=embeds.success("Removed that reminder."))

    @tasks.loop(seconds=30)
    async def _loop(self) -> None:
        for rid, uid, cid, message in await service.due():
            channel = self.bot.get_channel(cid)
            if isinstance(channel, (discord.TextChannel, discord.Thread)):
                try:
                    await channel.send(
                        f"<@{uid}>, reminder: {message}",
                        allowed_mentions=discord.AllowedMentions(users=True, everyone=False, roles=False),
                    )
                except discord.HTTPException:
                    pass
            await service.delete_one(rid)

    @_loop.before_loop
    async def _before(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ReminderCog(bot))
