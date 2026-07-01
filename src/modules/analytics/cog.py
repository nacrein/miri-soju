"""Command-usage tracking: one ledger row per completed command.

A single listener on ``on_command_completion`` (fires after a prefix command
finishes without error) appends a row via the analytics repository. It is
strictly best-effort — wrapped so a logging failure can never affect the command
the user just ran — and deliberately records only the command's qualified name,
the invoker, and the guild, never message content.

The data powers the dashboard's staff analytics; nothing in the bot reads it back.
"""

from __future__ import annotations

import logging

from discord.ext import commands

from src.database.session import get_session
from src.modules.analytics.repository import AnalyticsRepository

log = logging.getLogger(__name__)


class Analytics(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_completion(self, ctx: commands.Context) -> None:
        """Record a successful invocation. Never raises into the command flow."""
        if ctx.command is None:
            return
        try:
            async with get_session() as session:
                await AnalyticsRepository(session).record(
                    command=ctx.command.qualified_name,
                    user_id=ctx.author.id,
                    guild_id=ctx.guild.id if ctx.guild else None,
                )
        except Exception:
            log.exception("failed to record command usage for %s", ctx.command)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Analytics(bot))
