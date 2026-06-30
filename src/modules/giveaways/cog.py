"""Giveaways: timed, button-entry giveaways with an automatic winner draw.

The Enter button is a persistent DynamicItem, so entries survive restarts. A
background loop ends giveaways at their deadline and draws winners (the reminder
delivery-loop shape); reroll picks fresh winners from the existing entries."""

from __future__ import annotations

import random
from datetime import UTC, datetime

import discord
from discord.ext import commands, tasks

from src.core import embeds
from src.core.emojis import Emojis
from src.core.paginator import send_command_browser
from src.core.timeparse import parse_duration
from src.modules.giveaways import service
from src.modules.giveaways.views import GiveawayEnterButton, giveaway_view

_MAX_WINNERS = 50
_MAX_PRIZE = 256
_MENTIONS = discord.AllowedMentions(users=True, roles=False, everyone=False)


def _draw(entrant_ids: list[int], winners: int) -> list[int]:
    if not entrant_ids:
        return []
    return random.sample(entrant_ids, k=min(winners, len(entrant_ids)))


def _active_embed(prize: str, winners: int, ends_at: datetime, host) -> discord.Embed:
    return embeds.info(
        f"Click **Enter** below to join!\n\n"
        f"Ends {discord.utils.format_dt(ends_at, 'R')}\n"
        f"Winners: **{winners}**\nHosted by {host.mention}",
        f"{Emojis.TADA} {prize}",
    )


def _ended_embed(prize: str, winner_ids: list[int]) -> discord.Embed:
    won = ", ".join(f"<@{w}>" for w in winner_ids) if winner_ids else "No valid entries"
    return embeds.info(f"Winners: {won}", f"{Emojis.TADA} {prize} — Ended")


class Giveaways(commands.Cog, name="Giveaways"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._loop.start()

    async def cog_load(self) -> None:
        self.bot.add_dynamic_items(GiveawayEnterButton)

    def cog_unload(self) -> None:
        self._loop.cancel()

    @commands.group(name="giveaway", aliases=["gw"], invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def giveaway(self, ctx) -> None:
        """Run giveaways."""
        await send_command_browser(ctx, ctx.command)

    @giveaway.command(name="start")
    @commands.bot_has_permissions(send_messages=True)
    async def gw_start(self, ctx, duration: str, winners: int, *, prize: str) -> None:
        """Start a giveaway, e.g. `,giveaway start 1h 2 Discord Nitro`."""
        try:
            delta = parse_duration(duration)
        except ValueError as exc:
            raise commands.BadArgument(str(exc)) from exc
        if winners < 1 or winners > _MAX_WINNERS:
            raise commands.BadArgument(f"Winners must be between 1 and {_MAX_WINNERS}.")
        if len(prize) > _MAX_PRIZE:
            raise commands.BadArgument(f"Prize must be at most {_MAX_PRIZE} characters.")
        ends_at = datetime.now(UTC) + delta
        msg = await ctx.send(
            embed=_active_embed(prize, winners, ends_at, ctx.author), view=giveaway_view()
        )
        await service.create(
            ctx.guild.id, ctx.channel.id, msg.id, prize, winners, ends_at, ctx.author.id
        )

    @giveaway.command(name="end")
    async def gw_end(self, ctx, message_id: int) -> None:
        """End a giveaway now and draw its winners."""
        g = await self._owned(ctx, message_id)
        if g.ended:
            raise commands.BadArgument("That giveaway already ended.")
        await self._finish(g)
        await ctx.send(embed=embeds.success("Giveaway ended."))

    @giveaway.command(name="reroll")
    async def gw_reroll(self, ctx, message_id: int) -> None:
        """Reroll the winners of a giveaway."""
        g = await self._owned(ctx, message_id)
        winners = _draw(await service.entrants(g.id), g.winners)
        channel = self.bot.get_channel(g.channel_id)
        if not isinstance(channel, (discord.TextChannel, discord.Thread)):
            channel = ctx.channel
        await self._announce(channel, g.prize, winners, reroll=True)
        if channel.id != ctx.channel.id:
            await ctx.send(embed=embeds.success("Rerolled."))

    @giveaway.command(name="list")
    async def gw_list(self, ctx) -> None:
        """List active giveaways."""
        rows = await service.active_for(ctx.guild.id)
        if not rows:
            await ctx.send(embed=embeds.info("No active giveaways."))
            return
        lines = [
            f"`{g.message_id}` · **{g.prize}** · ends {discord.utils.format_dt(g.ends_at, 'R')}"
            for g in rows
        ]
        await ctx.send(embed=embeds.info("\n".join(lines), f"Active Giveaways ({len(rows)})"))

    async def _owned(self, ctx, message_id: int):
        g = await service.get_by_message(message_id)
        if g is None or g.guild_id != ctx.guild.id:
            raise commands.BadArgument("No giveaway with that message id in this server.")
        return g

    @tasks.loop(seconds=15)
    async def _loop(self) -> None:
        for g in await service.due():
            await self._finish(g)

    @_loop.before_loop
    async def _before(self) -> None:
        await self.bot.wait_until_ready()

    async def _finish(self, g) -> None:
        await service.mark_ended(g.id)
        channel = self.bot.get_channel(g.channel_id)
        if not isinstance(channel, (discord.TextChannel, discord.Thread)):
            return
        winners = _draw(await service.entrants(g.id), g.winners)
        try:
            msg = await channel.fetch_message(g.message_id)
            await msg.edit(embed=_ended_embed(g.prize, winners), view=None)
        except discord.HTTPException:
            pass
        await self._announce(channel, g.prize, winners, reroll=False)

    async def _announce(self, channel, prize: str, winners: list[int], *, reroll: bool) -> None:
        if not winners:
            await channel.send(embed=embeds.info(f"No one entered the giveaway for **{prize}**."))
            return
        mentions = ", ".join(f"<@{w}>" for w in winners)
        verb = "New winner(s)" if reroll else "Congratulations"
        await channel.send(
            f"{Emojis.TADA} {verb}: {mentions} — you won **{prize}**!",
            allowed_mentions=_MENTIONS,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Giveaways(bot))
