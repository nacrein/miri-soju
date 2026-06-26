"""Moderation commands: ban, unban, kick, timeout, untimeout, purge."""

from __future__ import annotations

import logging

import discord
from discord.ext import commands

from src.core import embeds
from src.modules.moderation import service
from src.modules.serverlog.service import log_event

log = logging.getLogger(__name__)

_DEFAULT_REASON = "No reason provided"


class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def _log(self, guild_id: int, embed: discord.Embed) -> None:
        await log_event(self.bot, guild_id, embed, "mod")

    @commands.hybrid_command(name="ban", extras={"example": "ban 123456789012345678 spamming"})
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    @commands.guild_only()
    async def ban(
        self, ctx: commands.Context, user: discord.User, *, reason: str = _DEFAULT_REASON
    ) -> None:
        """Ban a user by mention or ID (works even if they aren't in the server)."""
        member = ctx.guild.get_member(user.id)
        if member is not None:
            service.check_target(ctx, member)
        await ctx.guild.ban(user, reason=f"{ctx.author}: {reason}", delete_message_days=0)
        await ctx.send(embed=embeds.success(f"Banned **{user}**."))
        await self._log(ctx.guild.id, service.action_embed("Ban", ctx.author, user, reason))

    @commands.hybrid_command(name="unban", extras={"example": "unban 123456789012345678"})
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    @commands.guild_only()
    async def unban(
        self, ctx: commands.Context, user: discord.User, *, reason: str = _DEFAULT_REASON
    ) -> None:
        """Unban a previously banned user by ID or mention."""
        try:
            await ctx.guild.unban(user, reason=f"{ctx.author}: {reason}")
        except discord.NotFound:
            raise service.ModerationError("That user isn't banned.")
        await ctx.send(embed=embeds.success(f"Unbanned **{user}**."))
        await self._log(ctx.guild.id, service.action_embed("Unban", ctx.author, user, reason))

    @commands.hybrid_command(name="kick", extras={"example": "kick @user breaking rules"})
    @commands.has_permissions(kick_members=True)
    @commands.bot_has_permissions(kick_members=True)
    @commands.guild_only()
    async def kick(
        self, ctx: commands.Context, member: discord.Member, *, reason: str = _DEFAULT_REASON
    ) -> None:
        """Kick a member from the server."""
        service.check_target(ctx, member)
        await member.kick(reason=f"{ctx.author}: {reason}")
        await ctx.send(embed=embeds.success(f"Kicked **{member}**."))
        await self._log(ctx.guild.id, service.action_embed("Kick", ctx.author, member, reason))

    @commands.hybrid_command(name="timeout", extras={"example": "timeout @user 10m spam"})
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    @commands.guild_only()
    async def timeout(
        self,
        ctx: commands.Context,
        member: discord.Member,
        duration: str,
        *,
        reason: str = _DEFAULT_REASON,
    ) -> None:
        """Timeout a member for a duration like 10m, 2h, 1d."""
        service.check_target(ctx, member)
        delta = service.parse_duration(duration)
        await member.timeout(delta, reason=f"{ctx.author}: {reason}")
        await ctx.send(embed=embeds.success(f"Timed out **{member}** for {duration}."))
        await self._log(
            ctx.guild.id,
            service.action_embed(f"Timeout ({duration})", ctx.author, member, reason),
        )

    @commands.hybrid_command(name="untimeout", extras={"example": "untimeout @user"})
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    @commands.guild_only()
    async def untimeout(
        self, ctx: commands.Context, member: discord.Member, *, reason: str = _DEFAULT_REASON
    ) -> None:
        """Remove a member's timeout."""
        await member.timeout(None, reason=f"{ctx.author}: {reason}")
        await ctx.send(embed=embeds.success(f"Removed timeout from **{member}**."))
        await self._log(ctx.guild.id, service.action_embed("Untimeout", ctx.author, member, reason))

    @commands.hybrid_command(name="purge", extras={"example": "purge 50"})
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    @commands.guild_only()
    async def purge(self, ctx: commands.Context, amount: int) -> None:
        """Bulk-delete the last N messages (1-100) in this channel."""
        if amount < 1 or amount > 100:
            raise service.ModerationError("Amount must be between 1 and 100.")
        await ctx.defer(ephemeral=True)
        deleted = await ctx.channel.purge(limit=amount)
        await ctx.send(embed=embeds.success(f"Deleted {len(deleted)} message(s)."), ephemeral=True)
        embed = service.action_embed(
            "Purge", ctx.author, ctx.author, f"{len(deleted)} messages in #{ctx.channel}"
        )
        await self._log(ctx.guild.id, embed)


    # ── warnings ────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="warn", extras={"example": "warn @user spamming"})
    @commands.has_permissions(kick_members=True)
    @commands.guild_only()
    async def warn(
        self, ctx: commands.Context, member: discord.Member, *, reason: str = _DEFAULT_REASON
    ) -> None:
        """Warn a member. The warning is recorded for this server."""
        service.check_target(ctx, member, require_bot_higher=False)
        warning_id = await service.add_warning(ctx.guild.id, member.id, ctx.author.id, reason)
        count = len(await service.list_warnings(ctx.guild.id, member.id))
        await ctx.send(embed=embeds.success(
            f"Warned **{member}** (warning #{warning_id}). They now have **{count}** warning(s)."
        ))
        embed = service.action_embed(f"Warning #{warning_id}", ctx.author, member, reason)
        await self._log(ctx.guild.id, embed)

    @commands.hybrid_command(name="warnings", aliases=["warns"], extras={"example": "warnings @user"})
    @commands.has_permissions(kick_members=True)
    @commands.guild_only()
    async def warnings(self, ctx: commands.Context, member: discord.Member) -> None:
        """List a member's warnings in this server."""
        rows = await service.list_warnings(ctx.guild.id, member.id)
        if not rows:
            await ctx.send(embed=embeds.info(f"**{member}** has no warnings."))
            return
        lines = []
        for w in rows:
            when = discord.utils.format_dt(w.created_at, "R")
            lines.append(f"`#{w.id}` {w.reason or 'No reason'} — by <@{w.moderator_id}> · {when}")
        e = embeds.warning("\n".join(lines), f"{member.display_name}'s Warnings ({len(rows)})")
        await ctx.send(embed=e)

    @commands.hybrid_command(name="delwarn", extras={"example": "delwarn 12"})
    @commands.has_permissions(kick_members=True)
    @commands.guild_only()
    async def delwarn(self, ctx: commands.Context, warning_id: int) -> None:
        """Delete a single warning by its id."""
        ok = await service.delete_warning(ctx.guild.id, warning_id)
        if not ok:
            raise service.ModerationError("No warning with that id in this server.")
        await ctx.send(embed=embeds.success(f"Deleted warning #{warning_id}."))

    @commands.hybrid_command(name="clearwarnings", aliases=["clearwarns"], extras={"example": "clearwarnings @user"})
    @commands.has_permissions(kick_members=True)
    @commands.guild_only()
    async def clearwarnings(self, ctx: commands.Context, member: discord.Member) -> None:
        """Clear all of a member's warnings in this server."""
        count = await service.clear_warnings(ctx.guild.id, member.id)
        await ctx.send(embed=embeds.success(f"Cleared **{count}** warning(s) from {member.mention}."))

    # ── channel control ─────────────────────────────────────────────────────

    @commands.hybrid_command(name="lock", extras={"example": "lock raid in progress"})
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    @commands.guild_only()
    async def lock(self, ctx: commands.Context, *, reason: str = _DEFAULT_REASON) -> None:
        """Stop @everyone from sending messages in this channel."""
        overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
        if overwrite.send_messages is False:
            raise service.ModerationError("This channel is already locked.")
        overwrite.send_messages = False
        await ctx.channel.set_permissions(
            ctx.guild.default_role, overwrite=overwrite, reason=f"{ctx.author}: {reason}"
        )
        await ctx.send(embed=embeds.success(f"{Emojis.LOCK} Channel locked."))
        await self._log(ctx.guild.id, service.action_embed("Lock", ctx.author, ctx.author, f"#{ctx.channel}"))

    @commands.hybrid_command(name="unlock")
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    @commands.guild_only()
    async def unlock(self, ctx: commands.Context) -> None:
        """Restore @everyone's ability to send messages in this channel."""
        overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = None  # back to neutral (inherit default)
        await ctx.channel.set_permissions(
            ctx.guild.default_role, overwrite=overwrite, reason=f"Unlocked by {ctx.author}"
        )
        await ctx.send(embed=embeds.success(f"{Emojis.UNLOCK} Channel unlocked."))
        await self._log(ctx.guild.id, service.action_embed("Unlock", ctx.author, ctx.author, f"#{ctx.channel}"))

    @commands.hybrid_command(name="slowmode", aliases=["slow"], extras={"example": "slowmode 10"})
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    @commands.guild_only()
    async def slowmode(self, ctx: commands.Context, seconds: int) -> None:
        """Set this channel's slowmode delay in seconds (0 to disable, max 21600)."""
        if seconds < 0 or seconds > 21600:
            raise service.ModerationError("Slowmode must be between 0 and 21600 seconds (6 hours).")
        await ctx.channel.edit(slowmode_delay=seconds, reason=f"Set by {ctx.author}")
        if seconds == 0:
            await ctx.send(embed=embeds.success("Slowmode disabled."))
        else:
            await ctx.send(embed=embeds.success(f"Slowmode set to **{seconds}s**."))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Moderation(bot))
