"""Staff tools: economy faucet/sink, ledger inspection, and the staff roster.

Permission tiers (see ``src/core/checks.py``): owner > admin > staff.
  * The serious economy powers — minting (,give) and removing (,take) bits — are
    admin-gated. They exist both as top-level commands (the everyday spelling) and
    as ,staff give / ,staff take (the grouped spelling).
  * Roster management (,staff promote / demote) and the bot-wide blacklist
    (,staff blacklist / unblacklist) are admin-gated.
  * Everyday moderation is staff-gated: resetting a rule-breaker's balance
    (,staff reset), the economy blacklist (,staff econban / uneconban), and
    read-only inspection (,staff history / economy / error).
"""

from __future__ import annotations

import discord
from discord.ext import commands

from src.core import blacklist, checks, embeds, staff_roster
from src.core.checks import is_admin, is_staff
from src.core.emojis import Emojis
from src.core.error_log import get_error
from src.core.errors import BotError
from src.core.paginator import send_command_browser
from src.modules.economy import service


def _fmt(n: int) -> str:
    return f"{n:,}"


def _admin_or_hint(hint: str):
    """An admin gate that fails with a helpful ``BotError`` instead of the generic
    "you can't use that". Used on the top-level ,give/,take so a player who meant
    the money-transfer command is pointed at it rather than hitting a blank wall."""

    async def predicate(ctx: commands.Context) -> bool:
        if await checks._is_admin(ctx):
            return True
        raise BotError(hint)

    return commands.check(predicate)


class Staff(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ── shared bodies (top-level and grouped spellings both delegate here) ───────

    async def _do_grant(self, ctx: commands.Context, user: discord.User, amount: int) -> None:
        if user.bot:
            raise commands.BadArgument("Bots don't hold bits.")
        new_balance = await service.staff_grant(user.id, amount, ctx.author.id)
        await ctx.send(embed=embeds.success(
            f"Gave {Emojis.BITS} **{_fmt(amount)}** to {user.mention}. "
            f"Their wallet is now {Emojis.BITS} {_fmt(new_balance)}."
        ))

    async def _do_deduct(self, ctx: commands.Context, user: discord.User, amount: int) -> None:
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

    # ── top-level mint / sink (the everyday spelling) ────────────────────────────

    @commands.command(name="give", extras={"example": "give @user 500"})
    @_admin_or_hint(
        "Only staff admins can mint bits. Did you mean `,pay` to send someone bits "
        "from your own wallet?"
    )
    @commands.guild_only()
    async def give(self, ctx: commands.Context, user: discord.User, amount: int) -> None:
        """Mint bits straight into a user's wallet (staff faucet). Admin only."""
        await self._do_grant(ctx, user, amount)

    @commands.command(name="take", extras={"example": "take @user 500"})
    @is_admin()
    @commands.guild_only()
    async def take(self, ctx: commands.Context, user: discord.User, amount: int) -> None:
        """Remove bits from a user (staff sink; wallet first, then vault). Admin only."""
        await self._do_deduct(ctx, user, amount)

    # ── the ,staff console ───────────────────────────────────────────────────────

    @commands.group(name="staff", invoke_without_command=True)
    @is_staff()
    @commands.guild_only()
    async def staff(self, ctx: commands.Context) -> None:
        """Staff tools."""
        await send_command_browser(ctx, ctx.command)

    @staff.command(name="give", aliases=["grant", "add"])
    @is_admin()
    async def staff_give(self, ctx: commands.Context, user: discord.User, amount: int) -> None:
        """Mint bits straight into a user's wallet (staff faucet). Admin only."""
        await self._do_grant(ctx, user, amount)

    @staff.command(name="take", aliases=["remove", "deduct"])
    @is_admin()
    async def staff_take(self, ctx: commands.Context, user: discord.User, amount: int) -> None:
        """Remove bits from a user (staff sink; wallet first, then vault). Admin only."""
        await self._do_deduct(ctx, user, amount)

    @staff.command(name="reset", aliases=["wipe"])
    @is_staff()
    async def staff_reset(self, ctx: commands.Context, user: discord.User) -> None:
        """Wipe a user's balance (wallet + vault) to zero. Staff moderation tool."""
        if user.bot:
            raise commands.BadArgument("Bots don't hold bits.")
        cleared_wallet, cleared_vault = await service.staff_reset(user.id, ctx.author.id)
        total = cleared_wallet + cleared_vault
        parts = []
        if cleared_wallet:
            parts.append(f"{_fmt(cleared_wallet)} wallet")
        if cleared_vault:
            parts.append(f"{_fmt(cleared_vault)} vault")
        await ctx.send(embed=embeds.success(
            f"Reset {user.mention}'s balance, clearing {Emojis.BITS} **{_fmt(total)}** "
            f"({' + '.join(parts)})."
        ))

    # ── blacklists: bot-wide (admin) and economy-only (staff) ────────────────────

    @staff.command(name="blacklist", aliases=["bl"])
    @is_admin()
    async def staff_blacklist(
        self, ctx: commands.Context, user: discord.User, *, reason: str | None = None
    ) -> None:
        """Block a user from the entire bot. Admin only."""
        if user.bot:
            raise commands.BadArgument("Bots aren't users.")
        if user.id == ctx.author.id or await ctx.bot.is_owner(user):
            raise BotError("You can't blacklist yourself or the owner.")
        await blacklist.add(user.id, "bot", reason, ctx.author.id)
        suffix = f" Reason: {reason}" if reason else ""
        await ctx.send(embed=embeds.success(
            f"{Emojis.LOCK} Blacklisted {user.mention} from the bot.{suffix}"
        ))

    @staff.command(name="unblacklist", aliases=["unbl"])
    @is_admin()
    async def staff_unblacklist(self, ctx: commands.Context, user: discord.User) -> None:
        """Lift a user's bot-wide blacklist. Admin only."""
        if await blacklist.remove(user.id, "bot"):
            await ctx.send(embed=embeds.success(f"{user.mention} can use the bot again."))
        else:
            await ctx.send(embed=embeds.info(f"{user.mention} isn't blacklisted from the bot."))

    @staff.command(name="econban")
    @is_staff()
    async def staff_econban(
        self, ctx: commands.Context, user: discord.User, *, reason: str | None = None
    ) -> None:
        """Block a user from the economy only. Staff moderation tool."""
        if user.bot:
            raise commands.BadArgument("Bots don't use the economy.")
        if await ctx.bot.is_owner(user):
            raise BotError("You can't econban the owner.")
        await blacklist.add(user.id, "economy", reason, ctx.author.id)
        suffix = f" Reason: {reason}" if reason else ""
        await ctx.send(embed=embeds.success(
            f"{Emojis.LOCK} Blocked {user.mention} from the economy.{suffix}"
        ))

    @staff.command(name="uneconban")
    @is_staff()
    async def staff_uneconban(self, ctx: commands.Context, user: discord.User) -> None:
        """Lift a user's economy block. Staff moderation tool."""
        if await blacklist.remove(user.id, "economy"):
            await ctx.send(embed=embeds.success(f"{user.mention} can use the economy again."))
        else:
            await ctx.send(embed=embeds.info(f"{user.mention} isn't blocked from the economy."))

    @staff.command(name="promote")
    @is_admin()
    async def staff_promote(
        self, ctx: commands.Context, user: discord.User, tier: str | None = None
    ) -> None:
        """Grant a user staff, or `admin` (owner only), e.g. ,staff promote @u admin."""
        if user.bot:
            raise commands.BadArgument("Bots can't be staff.")
        requested = "admin" if (tier or "").lower() in ("admin", "a") else "staff"
        is_owner = await ctx.bot.is_owner(ctx.author)
        current = await staff_roster.get_tier(user.id)
        if requested == "admin" and not is_owner:
            raise BotError("Only the owner can grant the admin tier.")
        if current == "admin" and not is_owner:
            raise BotError("Only the owner can change an admin's tier.")
        if current == requested:
            await ctx.send(embed=embeds.info(f"{user.mention} is already **{requested}**."))
            return
        await staff_roster.set_tier(user.id, requested, ctx.author.id)
        badge = Emojis.CROWN if requested == "admin" else Emojis.SHIELD
        await ctx.send(embed=embeds.success(f"{badge} {user.mention} is now **{requested}**."))

    @staff.command(name="demote")
    @is_admin()
    async def staff_demote(self, ctx: commands.Context, user: discord.User) -> None:
        """Revoke a user's staff/admin tier (demoting an admin is owner only)."""
        current = await staff_roster.get_tier(user.id)
        if current == "admin" and not await ctx.bot.is_owner(ctx.author):
            raise BotError("Only the owner can demote an admin.")
        removed = await staff_roster.remove(user.id)
        if not removed:
            if user.id in checks._staff_ids():
                raise BotError(
                    "That user is pinned as staff via the `STAFF_IDS` env config; "
                    "remove them there and restart to revoke it."
                )
            await ctx.send(embed=embeds.info(f"{user.mention} isn't on the staff roster."))
            return
        await ctx.send(embed=embeds.success(
            f"Removed {user.mention} from staff (was **{current}**)."
        ))

    @staff.command(name="roster", aliases=["list"])
    @is_staff()
    async def staff_roster_cmd(self, ctx: commands.Context) -> None:
        """Show the current admins and staff."""
        rows = await staff_roster.list_roster()
        admins = [r.discord_id for r in rows if r.tier == "admin"]
        members = [r.discord_id for r in rows if r.tier == "staff"]
        legacy = sorted(checks._staff_ids() - {r.discord_id for r in rows})

        def _mentions(ids: list[int]) -> str:
            return ", ".join(f"<@{i}>" for i in ids) if ids else "None"

        e = embeds.info("", f"{Emojis.SHIELD} Staff Roster")
        e.add_field(name=f"{Emojis.CROWN} Admins", value=_mentions(admins), inline=False)
        e.add_field(name=f"{Emojis.SHIELD} Staff", value=_mentions(members), inline=False)
        if legacy:
            e.add_field(name="Legacy (env STAFF_IDS)", value=_mentions(legacy), inline=False)
        await ctx.send(embed=e)

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
