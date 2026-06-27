"""AFK: mark yourself away. The bot announces it when you're pinged and clears it
when you speak again. State is in-memory and per server, so it resets on restart.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import discord
from discord.ext import commands

from src.core import embeds

_MAX_REASON = 200


@dataclass
class _Afk:
    reason: str
    since: datetime
    # The message that set AFK, so that very message doesn't immediately clear it
    # (listener vs. command ordering is not guaranteed; the id is invariant).
    set_by_message: int


class Afk(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._afk: dict[tuple[int, int], _Afk] = {}  # (guild_id, user_id) -> state

    @commands.command(name="afk", extras={"example": "afk lunch, back soon"})
    @commands.guild_only()
    async def afk(self, ctx: commands.Context, *, reason: str = "AFK") -> None:
        """Mark yourself AFK. I'll tell anyone who pings you."""
        reason = reason[:_MAX_REASON]
        self._afk[(ctx.guild.id, ctx.author.id)] = _Afk(
            reason=reason, since=discord.utils.utcnow(), set_by_message=ctx.message.id
        )
        await ctx.send(embed=embeds.success(f"You're now AFK: {reason}"))

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.guild is None or message.author.bot:
            return

        # The author is back — clear their AFK, but never on the message that set it.
        key = (message.guild.id, message.author.id)
        entry = self._afk.get(key)
        if entry is not None and message.id != entry.set_by_message:
            del self._afk[key]
            await message.channel.send(
                embed=embeds.info(f"Welcome back, {message.author.mention} — cleared your AFK."),
                delete_after=10,
            )

        # Someone pinged AFK members — announce them in one message.
        notices = []
        for user in message.mentions:
            pinged = self._afk.get((message.guild.id, user.id))
            if pinged is not None:
                ago = discord.utils.format_dt(pinged.since, "R")
                notices.append(f"{user.display_name} is AFK ({ago}): {pinged.reason}")
        if notices:
            await message.channel.send(embed=embeds.info("\n".join(notices)))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Afk(bot))
