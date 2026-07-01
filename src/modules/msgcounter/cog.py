"""Cross-server message tracking for moderation.

An ``on_message`` listener tallies how many messages each user sends in each guild
the bot is in. Counts accumulate in memory and flush to the DB every 30s in one
batched transaction — far cheaper than a write per message, and a restart drops at
most the last window (fine for a moderation stat). ``,messages @user`` (staff only)
lists the servers a user is active in, busiest first, with per-server counts.

Only servers the bot is currently in are shown — a stored guild the bot has since
left is hidden rather than surfaced as a bare id.
"""

from __future__ import annotations

import logging
from collections import Counter

import discord
from discord.ext import commands, tasks

from src.core import embeds
from src.core.checks import is_staff
from src.core.emojis import Emojis
from src.core.paginator import Paginator, paginate_lines
from src.database.session import get_session
from src.modules.msgcounter.repository import MsgCountRepository

log = logging.getLogger(__name__)


class MsgCounter(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        # (guild_id, user_id) -> messages seen since the last flush.
        self._pending: Counter[tuple[int, int]] = Counter()
        self._flush.start()

    def cog_unload(self) -> None:
        self._flush.cancel()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or message.guild is None:
            return
        self._pending[(message.guild.id, message.author.id)] += 1

    @tasks.loop(seconds=30)
    async def _flush(self) -> None:
        """Write the accumulated per-(guild, user) counts in one batched transaction."""
        if not self._pending:
            return
        batch = self._pending
        self._pending = Counter()  # swap out so new messages accrue against a fresh tally
        try:
            async with get_session() as session:
                repo = MsgCountRepository(session)
                for (guild_id, user_id), delta in batch.items():
                    await repo.bump(guild_id, user_id, delta)
        except Exception:
            # Don't lose the batch on a transient DB error: fold it back in.
            self._pending.update(batch)
            log.exception("failed to flush %d message-count buckets", len(batch))

    @_flush.before_loop
    async def _before_flush(self) -> None:
        await self.bot.wait_until_ready()

    @commands.command(name="messages", aliases=["msgs", "seen"])
    @is_staff()
    async def messages(self, ctx: commands.Context, user: discord.User) -> None:
        """Where a user is active: their message count in every server Miri shares with them."""
        async with get_session() as session:
            rows = await MsgCountRepository(session).by_user(user.id)

        present: list[tuple[discord.Guild, int]] = []
        for guild_id, count in rows:
            guild = self.bot.get_guild(guild_id)
            if guild is not None:  # only servers the bot is currently in
                present.append((guild, count))

        if not present:
            await ctx.send(embed=embeds.info(
                f"No tracked messages from {user.mention} in any server I'm in."
            ))
            return

        total = sum(count for _, count in present)
        lines = [f"**{guild.name}** · {count:,}" for guild, count in present]
        title = f"{Emojis.MESSAGE} {user.display_name} · {total:,} messages in {len(present)} servers"
        await Paginator(ctx.author.id, paginate_lines(lines, title)).start(ctx)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MsgCounter(bot))
