"""Staff tools: the staff roster, the bot-wide blacklist, and error diagnosis.

Permission tiers (see ``src/core/checks.py``): owner > admin > staff.
  * Roster management (,staff promote / demote) and the bot-wide blacklist
    (,staff blacklist / unblacklist) are admin-gated.
  * Read-only inspection (,staff roster / error) is staff-gated.
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


class Staff(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.group(name="staff", invoke_without_command=True)
    @is_staff()
    @commands.guild_only()
    async def staff(self, ctx: commands.Context) -> None:
        """Staff tools."""
        await send_command_browser(ctx, ctx.command)

    # ── bot-wide blacklist (admin) ───────────────────────────────────────────────

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

    # ── roster management ────────────────────────────────────────────────────────

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
