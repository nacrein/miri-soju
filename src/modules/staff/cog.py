"""Staff-only moderation tools: economy ledger inspection."""

from __future__ import annotations

import discord
from discord.ext import commands

from src.core import embeds
from src.core.checks import is_staff
from src.core.emojis import Emojis
from src.modules.economy import service


def _fmt(n: int) -> str:
    return f"{n:,}"


class Staff(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.command(name="history")
    @is_staff()
    async def history(self, ctx: commands.Context, user: discord.User, page: int = 1) -> None:
        """Staff: view a user's economy transaction history."""
        page = max(1, page)
        per = 15
        rows, total = await service.get_history(user.id, limit=per, offset=(page - 1) * per)
        if not rows:
            await ctx.send(embed=embeds.info(f"No transactions for {user.mention}."))
            return
        lines = []
        for t in rows:
            sign = "+" if t.amount >= 0 else "−"
            stamp = discord.utils.format_dt(t.created_at, "R")
            extra = f" ↔ <@{t.counterparty_id}>" if t.counterparty_id else ""
            note = f" ({t.note})" if t.note else ""
            lines.append(
                f"`{t.kind}` {sign}{_fmt(abs(t.amount))} → bal {_fmt(t.balance_after)}{extra}{note} · {stamp}"
            )
        pages = (total + per - 1) // per
        e = embeds.info("\n".join(lines), f"{Emojis.RANK} {user.display_name}'s Ledger")
        e.set_footer(text=f"Page {page}/{pages} · {total} total transactions")
        await ctx.send(embed=e)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Staff(bot))
