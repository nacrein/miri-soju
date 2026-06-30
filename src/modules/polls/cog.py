"""Polls: a button-vote poll with a live tally.

`,poll create Question? | Option A | Option B` posts the poll; each option is a
persistent button (one vote per person, changeable). `,poll end` closes it and
freezes the result. Buttons survive restarts via a DynamicItem keyed by message id."""

from __future__ import annotations

import discord
from discord.ext import commands

from src.core import embeds
from src.core.paginator import send_command_browser
from src.modules.polls import service
from src.modules.polls.views import PollVoteButton, poll_embed, poll_view

_MAX_QUESTION = 256
_MAX_OPTION = 100
_MIN_OPTIONS = 2
_MAX_OPTIONS = 10


class Polls(commands.Cog, name="Polls"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        self.bot.add_dynamic_items(PollVoteButton)

    @commands.group(name="poll", invoke_without_command=True)
    @commands.guild_only()
    async def poll(self, ctx) -> None:
        """Create and manage polls."""
        await send_command_browser(ctx, ctx.command)

    @poll.command(name="create", aliases=["new", "start"])
    @commands.bot_has_permissions(send_messages=True)
    async def poll_create(self, ctx, *, text: str) -> None:
        """Create a poll: `,poll create Question? | Option A | Option B`."""
        parts = [p.strip() for p in text.split("|") if p.strip()]
        if len(parts) < _MIN_OPTIONS + 1:
            raise commands.BadArgument(
                "Format: `,poll create Question? | Option A | Option B` (2+ options)."
            )
        question, options = parts[0], parts[1:]
        if len(question) > _MAX_QUESTION:
            raise commands.BadArgument(f"Question is at most {_MAX_QUESTION} characters.")
        if len(options) > _MAX_OPTIONS:
            raise commands.BadArgument(f"At most {_MAX_OPTIONS} options.")
        if any(len(o) > _MAX_OPTION for o in options):
            raise commands.BadArgument(f"Each option is at most {_MAX_OPTION} characters.")
        # Send first to get a message id, then attach buttons keyed by that id.
        placeholder = _PollStub(question)
        msg = await ctx.send(embed=poll_embed(placeholder, options, {}))
        await service.create(
            ctx.guild.id, ctx.channel.id, msg.id, ctx.author.id, question, options
        )
        await msg.edit(view=poll_view(msg.id, options))

    @poll.command(name="end", aliases=["close"])
    async def poll_end(self, ctx, message_id: int) -> None:
        """Close a poll and freeze its result (poll author or Manage Messages)."""
        poll = await service.get_by_message(message_id)
        if poll is None or poll.guild_id != ctx.guild.id:
            raise commands.BadArgument("No poll with that message id in this server.")
        if poll.closed:
            raise commands.BadArgument("That poll is already closed.")
        if poll.author_id != ctx.author.id and not ctx.author.guild_permissions.manage_messages:
            raise commands.BadArgument("Only the poll's author or a mod can close it.")
        await service.close(poll.id)
        data = await service.render_data(message_id)
        if data is not None:
            closed_poll, options, counts = data
            channel = self.bot.get_channel(closed_poll.channel_id)
            if isinstance(channel, (discord.TextChannel, discord.Thread)):
                try:
                    msg = await channel.fetch_message(message_id)
                    await msg.edit(embed=poll_embed(closed_poll, options, counts), view=None)
                except discord.HTTPException:
                    pass
        await ctx.send(embed=embeds.success("Poll closed."))


class _PollStub:
    """A not-yet-saved poll, so the first embed renders before the row exists."""

    closed = False

    def __init__(self, question: str) -> None:
        self.question = question


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Polls(bot))
