"""Staff-only moderation tools: economy ledger inspection."""

from __future__ import annotations

import discord
from discord.ext import commands

from src.core import embeds
from src.core.checks import is_staff
from src.core.emojis import Emojis
from src.core.error_log import get_error
from src.core.errors import BotError
from src.core.paginator import send_command_browser
from src.modules.economy import service


def _fmt(n: int) -> str:
    return f"{n:,}"


class Staff(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.group(name="staff", invoke_without_command=True)
    @is_staff()
    @commands.guild_only()
    async def staff(self, ctx: commands.Context) -> None:
        """Staff tools."""
        await send_command_browser(ctx, ctx.command)

    @staff.command(name="history")
    @is_staff()
    async def staff_history(self, ctx: commands.Context, user: discord.User, page: int = 1) -> None:
        """A user's economy transaction history."""
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

    @staff.command(name="give", aliases=["grant", "add"])
    @is_staff()
    async def staff_give(self, ctx: commands.Context, user: discord.User, amount: int) -> None:
        """Mint bits straight into a user's wallet (staff faucet)."""
        if user.bot:
            raise commands.BadArgument("Bots don't hold bits.")
        new_balance = await service.staff_grant(user.id, amount, ctx.author.id)
        await ctx.send(embed=embeds.success(
            f"Gave {Emojis.BITS} **{_fmt(amount)}** to {user.mention}. "
            f"Their wallet is now {Emojis.BITS} {_fmt(new_balance)}."
        ))

    @staff.command(name="take", aliases=["remove", "deduct"])
    @is_staff()
    async def staff_take(self, ctx: commands.Context, user: discord.User, amount: int) -> None:
        """Remove bits from a user (staff sink; takes wallet first, then vault)."""
        if user.bot:
            raise commands.BadArgument("Bots don't hold bits.")
        from_wallet, from_vault = await service.staff_deduct(user.id, amount, ctx.author.id)
        total = from_wallet + from_vault
        parts = []
        if from_wallet:
            parts.append(f"{_fmt(from_wallet)} wallet")
        if from_vault:
            parts.append(f"{_fmt(from_vault)} vault")
        msg = f"Took {Emojis.BITS} **{_fmt(total)}** from {user.mention} ({' + '.join(parts)})."
        if total < amount:
            msg += " That was everything they had."
        await ctx.send(embed=embeds.success(msg))

    @staff.command(name="economy", aliases=["eco"])
    @is_staff()
    async def staff_economy(self, ctx: commands.Context) -> None:
        """Server-wide economy totals: circulation, holdings, player count."""
        t = await service.economy_totals()
        e = embeds.info("", f"{Emojis.RANK} Economy Overview")
        e.add_field(name="Players", value=_fmt(t["players"]))
        e.add_field(name="In Circulation", value=f"{Emojis.BITS} {_fmt(t['circulation'])}")
        e.add_field(name="Wallets", value=f"{Emojis.BITS} {_fmt(t['wallet_total'])}")
        e.add_field(name="Vaults", value=f"{Emojis.BANK} {_fmt(t['vault_total'])}")
        await ctx.send(embed=e)

    @staff.command(name="error", aliases=["err", "diagnose"])
    @is_staff()
    async def staff_error(self, ctx: commands.Context, code: str) -> None:
        """Diagnose a logged error by its code, e.g. ,staff error 7187AE."""
        code = code.strip().upper().removeprefix("#")
        record = await get_error(code)
        if record is None:
            raise BotError(
                f"No error logged with code `{code}`. Only unexpected bugs get a code "
                "(plain validation messages don't)."
            )
        e = embeds.error(f"Diagnostics for error `{record.code}`.", "Error report")
        when = discord.utils.format_dt(record.created_at, "R")
        e.add_field(name="When", value=when, inline=False)
        e.add_field(name="Where", value=f"`{record.context}`", inline=False)
        e.add_field(name="Type", value=record.exc_type)
        if record.guild_id:
            e.add_field(name="Guild", value=str(record.guild_id))
        if record.user_id:
            e.add_field(name="User", value=f"<@{record.user_id}>")
        e.add_field(name="Message", value=f"```\n{record.message[:980]}\n```", inline=False)
        if record.traceback:
            tail = f"```py\n{record.traceback[-950:]}\n```"
            e.add_field(name="Traceback (tail)", value=tail, inline=False)
        await ctx.send(embed=e)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Staff(bot))
