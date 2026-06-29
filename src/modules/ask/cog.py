"""ask: ask the AI a question via the Anthropic Messages API."""

from __future__ import annotations

import anthropic
import discord
from discord.ext import commands

from src.core.errors import BotError
from src.modules.ask import service

_MAX_LEN = 2000  # Discord message length limit


class Ask(commands.Cog, name="Ask"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.command(
        name="ask",
        aliases=["ai", "gpt"],
        extras={"example": "ask what's the capital of France?"},
    )
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def ask(self, ctx: commands.Context, *, prompt: str) -> None:
        """Ask the AI a question."""
        async with ctx.typing():
            try:
                answer = await service.ask(self.bot, ctx.author.id, prompt)
            except anthropic.RateLimitError:
                raise BotError("The AI is busy right now — try again in a moment.")
            except anthropic.APIError:
                raise BotError("Couldn't reach the AI right now — try again shortly.")
        await ctx.send(answer[:_MAX_LEN], allowed_mentions=discord.AllowedMentions.none())


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Ask(bot))
