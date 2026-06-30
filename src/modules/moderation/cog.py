"""Moderation commands: ban, unban, kick, timeout, untimeout, purge."""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime, timedelta

import discord
from discord.ext import commands, tasks

from src.core import embeds
from src.core.emojis import Emojis
from src.core.paginator import send_command_browser
from src.modules.moderation import service
from src.modules.serverlog.service import log_event

log = logging.getLogger(__name__)

_DEFAULT_REASON = "No reason provided"

_ACTION_ICONS = {
    "Ban": Emojis.BAN, "Unban": Emojis.UNBAN, "Kick": Emojis.KICK,
    "Timeout": Emojis.TIMEOUT, "Untimeout": Emojis.UNTIMEOUT, "Purge": Emojis.PURGE,
}


def check_target(
    ctx: commands.Context,
    target: discord.Member,
    *,
    require_bot_higher: bool = True,
) -> None:
    """Raise ModerationError if the moderator (or bot) can't action this member.

    require_bot_higher=False for actions the bot doesn't enact on Discord (e.g. warn).
    """
    if target == ctx.author:
        raise service.ModerationError("You can't target yourself.")
    if target == ctx.guild.me:
        raise service.ModerationError("I can't target myself.")
    if target.id == ctx.guild.owner_id:
        raise service.ModerationError("You can't target the server owner.")
    # Moderator hierarchy (the guild owner bypasses this).
    if ctx.author.id != ctx.guild.owner_id and target.top_role >= ctx.author.top_role:
        raise service.ModerationError("That member is equal to or above you in the role hierarchy.")
    # Bot hierarchy: the bot's top role must be above the target's.
    if require_bot_higher and target.top_role >= ctx.guild.me.top_role:
        raise service.ModerationError("That member is above me in the role hierarchy.")


def action_embed(
    action: str,
    moderator: discord.abc.User,
    target: discord.abc.User,
    reason: str,
) -> discord.Embed:
    """Build the mod-action embed posted to the audit channel."""
    icon = _ACTION_ICONS.get(action.split()[0], Emojis.SHIELD)
    e = discord.Embed(title=f"{icon} {action}", color=discord.Color.dark_red())
    e.add_field(name="Member", value=f"{target} (`{target.id}`)", inline=False)
    e.add_field(name="Moderator", value=str(moderator), inline=False)
    e.add_field(name="Reason", value=reason, inline=False)
    e.timestamp = discord.utils.utcnow()
    return e


class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._temprole_loop.start()

    async def cog_load(self) -> None:
        from src.core.setup_registry import SetupEntry, register_setup
        from src.modules.moderation.setup_view import ModerationSetupView

        register_setup(SetupEntry(
            key="moderation", label="Moderation", emoji=Emojis.SHIELD,
            description="Set the jail role used by ,jail.",
            factory=lambda author_id, guild_id: ModerationSetupView(author_id, guild_id),
        ))

    def cog_unload(self) -> None:
        from src.core.setup_registry import unregister_setup

        self._temprole_loop.cancel()
        unregister_setup("moderation")

    async def _log(self, guild_id: int, embed: discord.Embed) -> None:
        await log_event(self.bot, guild_id, embed, "mod")

    async def _guard(self, ctx, target, *, require_bot_higher: bool = True) -> None:
        """check_target plus the immune list. Run before any enforcement action."""
        if isinstance(target, discord.Member):
            check_target(ctx, target, require_bot_higher=require_bot_higher)
        role_ids = [r.id for r in target.roles] if isinstance(target, discord.Member) else []
        if await service.is_immune(ctx.guild.id, target.id, role_ids):
            raise service.ModerationError("That user is on the immune list and can't be actioned.")

    @tasks.loop(seconds=60)
    async def _temprole_loop(self) -> None:
        # Collect the ids we can safely retire and batch-delete them in one session.
        # A row is kept (retried next cycle) only when Discord removal genuinely failed.
        done: list[int] = []
        for entry_id, gid, uid, rid in await service.due_temproles():
            guild = self.bot.get_guild(gid)
            member = guild.get_member(uid) if guild is not None else None
            role = guild.get_role(rid) if guild is not None else None
            if member is not None and role is not None and role in member.roles:
                try:
                    await member.remove_roles(role, reason="temprole expired")
                except discord.HTTPException:
                    continue  # leave the row so it's retried next cycle
            # Removed, or the guild/member/role/assignment is gone: retire the row.
            done.append(entry_id)
        await service.delete_temproles(done)

    @_temprole_loop.before_loop
    async def _before_temprole_loop(self) -> None:
        await self.bot.wait_until_ready()

    @commands.hybrid_command(name="ban", extras={"example": "ban 123456789012345678 spamming"})
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    @commands.guild_only()
    async def ban(
        self, ctx: commands.Context, user: discord.User, *, reason: str = _DEFAULT_REASON
    ) -> None:
        """Ban a user by mention or ID (works even if they aren't in the server)."""
        member = ctx.guild.get_member(user.id)
        await self._guard(ctx, member or user)
        await ctx.guild.ban(user, reason=f"{ctx.author}: {reason}", delete_message_days=0)
        await service.add_case(ctx.guild.id, user.id, ctx.author.id, "ban", reason)
        await ctx.send(embed=embeds.success(f"Banned **{user}**."))
        await self._log(ctx.guild.id, action_embed("Ban", ctx.author, user, reason))

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
            raise service.ModerationError("That user isn't banned.") from None
        await service.add_case(ctx.guild.id, user.id, ctx.author.id, "unban", reason)
        await ctx.send(embed=embeds.success(f"Unbanned **{user}**."))
        await self._log(ctx.guild.id, action_embed("Unban", ctx.author, user, reason))

    @commands.hybrid_command(name="softban", extras={"example": "softban @user clearing spam"})
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    @commands.guild_only()
    async def softban(
        self, ctx: commands.Context, member: discord.Member, *, reason: str = _DEFAULT_REASON
    ) -> None:
        """Ban then immediately unban to clear a member's recent messages."""
        await self._guard(ctx, member)
        await ctx.guild.ban(
            member, reason=f"{ctx.author} (softban): {reason}", delete_message_days=1
        )
        await ctx.guild.unban(member, reason=f"{ctx.author}: softban cleanup")
        await ctx.send(embed=embeds.success(f"Softbanned **{member}** (recent messages cleared)."))
        await self._log(ctx.guild.id, action_embed("Softban", ctx.author, member, reason))

    @commands.command(name="massban", extras={"example": "massban 123 456 789"})
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    @commands.guild_only()
    async def massban(self, ctx: commands.Context, *user_ids: int) -> None:
        """Ban many users by ID at once (asks for confirmation)."""
        if not user_ids:
            raise service.ModerationError("Give one or more user IDs to ban.")
        if len(user_ids) > 50:
            raise service.ModerationError("Limit massban to 50 IDs at a time.")
        prompt = await ctx.send(embed=embeds.warning(
            f"Ban **{len(user_ids)}** user(s) by ID? Reply `yes` to confirm."
        ))

        def check(m: discord.Message) -> bool:
            return (
                m.author == ctx.author
                and m.channel == ctx.channel
                and m.content.lower() == "yes"
            )

        try:
            await self.bot.wait_for("message", check=check, timeout=30)
        except TimeoutError:
            await prompt.edit(embed=embeds.info("Cancelled."))
            return

        banned = 0
        for uid in user_ids:
            try:
                await ctx.guild.ban(discord.Object(id=uid), reason=f"{ctx.author}: massban")
                banned += 1
            except discord.HTTPException:
                continue
        await ctx.send(embed=embeds.success(f"Banned **{banned}** of {len(user_ids)} user(s)."))
        await self._log(
            ctx.guild.id, action_embed("Massban", ctx.author, ctx.author, f"{banned} users")
        )

    @commands.hybrid_command(name="kick", extras={"example": "kick @user breaking rules"})
    @commands.has_permissions(kick_members=True)
    @commands.bot_has_permissions(kick_members=True)
    @commands.guild_only()
    async def kick(
        self, ctx: commands.Context, member: discord.Member, *, reason: str = _DEFAULT_REASON
    ) -> None:
        """Kick a member from the server."""
        await self._guard(ctx, member)
        await member.kick(reason=f"{ctx.author}: {reason}")
        await service.add_case(ctx.guild.id, member.id, ctx.author.id, "kick", reason)
        await ctx.send(embed=embeds.success(f"Kicked **{member}**."))
        await self._log(ctx.guild.id, action_embed("Kick", ctx.author, member, reason))

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
        await self._guard(ctx, member)
        delta = service.parse_duration(duration)
        await member.timeout(delta, reason=f"{ctx.author}: {reason}")
        await service.add_case(ctx.guild.id, member.id, ctx.author.id, "timeout", f"{duration}: {reason}")
        await ctx.send(embed=embeds.success(f"Timed out **{member}** for {duration}."))
        await self._log(
            ctx.guild.id,
            action_embed(f"Timeout ({duration})", ctx.author, member, reason),
        )

    @commands.hybrid_command(name="untimeout", extras={"example": "untimeout @user"})
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    @commands.guild_only()
    async def untimeout(
        self, ctx: commands.Context, member: discord.Member, *, reason: str = _DEFAULT_REASON
    ) -> None:
        """Remove a member's timeout."""
        await self._guard(ctx, member)
        await member.timeout(None, reason=f"{ctx.author}: {reason}")
        await service.add_case(ctx.guild.id, member.id, ctx.author.id, "untimeout", reason)
        await ctx.send(embed=embeds.success(f"Removed timeout from **{member}**."))
        await self._log(ctx.guild.id, action_embed("Untimeout", ctx.author, member, reason))

    @commands.group(name="purge", aliases=["clear", "prune"], invoke_without_command=True)
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    @commands.guild_only()
    async def purge(self, ctx, amount: int | None = None) -> None:
        """Delete the last n messages. Subcommands filter by type."""
        if amount is None:
            await send_command_browser(ctx, ctx.command)
            return
        await self._purge(ctx, amount)

    @purge.command(name="bots")
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def purge_bots(self, ctx, amount: int = 100) -> None:
        """Messages from bots."""
        await self._purge(ctx, amount, check=lambda m: m.author.bot)

    @purge.command(name="humans")
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def purge_humans(self, ctx, amount: int = 100) -> None:
        """Messages not from bots."""
        await self._purge(ctx, amount, check=lambda m: not m.author.bot)

    @purge.command(name="links")
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def purge_links(self, ctx, amount: int = 100) -> None:
        """Messages containing links."""
        await self._purge(ctx, amount, check=lambda m: bool(re.search(r"https?://", m.content)))

    @purge.command(name="images")
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def purge_images(self, ctx, amount: int = 100) -> None:
        """Messages with image attachments."""
        await self._purge(
            ctx, amount,
            check=lambda m: any(
                a.content_type and a.content_type.startswith("image") for a in m.attachments
            ),
        )

    @purge.command(name="files")
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def purge_files(self, ctx, amount: int = 100) -> None:
        """Messages with any attachment."""
        await self._purge(ctx, amount, check=lambda m: bool(m.attachments))

    @purge.command(name="embeds")
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def purge_embeds(self, ctx, amount: int = 100) -> None:
        """Messages with embeds."""
        await self._purge(ctx, amount, check=lambda m: bool(m.embeds))

    @purge.command(name="mentions")
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def purge_mentions(self, ctx, amount: int = 100) -> None:
        """Messages with mentions."""
        await self._purge(ctx, amount, check=lambda m: bool(m.mentions or m.role_mentions))

    @purge.command(name="invites")
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def purge_invites(self, ctx, amount: int = 100) -> None:
        """Messages with server invites."""
        await self._purge(
            ctx, amount,
            check=lambda m: bool(re.search(r"discord(?:\.gg|(?:app)?\.com/invite)/", m.content)),
        )

    @purge.command(name="contains")
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def purge_contains(self, ctx, *, text: str) -> None:
        """Messages containing a substring (min 3 chars)."""
        if len(text) < 3:
            raise service.ModerationError("Give at least 3 characters.")
        await self._purge(ctx, 100, check=lambda m: text.lower() in m.content.lower())

    @purge.command(name="startswith", aliases=["prefix"])
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def purge_startswith(self, ctx, *, text: str) -> None:
        """Messages starting with a substring (min 3 chars)."""
        if len(text) < 3:
            raise service.ModerationError("Give at least 3 characters.")
        await self._purge(ctx, 100, check=lambda m: m.content.lower().startswith(text.lower()))

    @purge.command(name="endswith", aliases=["suffix"])
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def purge_endswith(self, ctx, *, text: str) -> None:
        """Messages ending with a substring (min 3 chars)."""
        if len(text) < 3:
            raise service.ModerationError("Give at least 3 characters.")
        await self._purge(ctx, 100, check=lambda m: m.content.lower().endswith(text.lower()))

    @purge.command(name="user", aliases=["member"])
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def purge_user(self, ctx, user: discord.User, amount: int = 100) -> None:
        """Messages from one member."""
        await self._purge(ctx, amount, check=lambda m: m.author.id == user.id)

    @purge.command(name="before")
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def purge_before(self, ctx, message: discord.Message, amount: int = 100) -> None:
        """Messages before a target message."""
        await self._purge(ctx, amount, before=message)

    @purge.command(name="after")
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def purge_after(self, ctx, message: discord.Message, amount: int = 100) -> None:
        """Messages after a target message."""
        await self._purge(ctx, amount, after=message)

    @purge.command(name="between")
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def purge_between(
        self, ctx, start: discord.Message, end: discord.Message, amount: int = 100
    ) -> None:
        """Messages between two target messages."""
        await self._purge(ctx, amount, after=start, before=end)


    # ── warnings ────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="warn", extras={"example": "warn @user spamming"})
    @commands.has_permissions(kick_members=True)
    @commands.guild_only()
    async def warn(
        self, ctx: commands.Context, member: discord.Member, *, reason: str = _DEFAULT_REASON
    ) -> None:
        """Warn a member. The warning is recorded for this server."""
        await self._guard(ctx, member, require_bot_higher=False)
        case_id = await service.add_case(ctx.guild.id, member.id, ctx.author.id, "warn", reason)
        count = len(await service.list_warnings(ctx.guild.id, member.id))
        await ctx.send(embed=embeds.success(
            f"Warned **{member}** (case #{case_id}). They now have **{count}** warning(s)."
        ))
        await self._log(ctx.guild.id, action_embed(f"Warning #{case_id}", ctx.author, member, reason))

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
            lines.append(f"`#{w.id}` {w.reason or 'No reason'} · by <@{w.moderator_id}> · {when}")
        e = embeds.warning("\n".join(lines), f"{member.display_name}'s Warnings ({len(rows)})")
        await ctx.send(embed=e)

    @commands.hybrid_command(name="clearwarnings", aliases=["clearwarns"], extras={"example": "clearwarnings @user"})
    @commands.has_permissions(kick_members=True)
    @commands.guild_only()
    async def clearwarnings(self, ctx: commands.Context, member: discord.Member) -> None:
        """Clear all of a member's warnings in this server."""
        count = await service.clear_warnings(ctx.guild.id, member.id)
        await ctx.send(embed=embeds.success(f"Cleared **{count}** warning(s) from {member.mention}."))

    # ── notes & history ───────────────────────────────────────────────────────

    @commands.group(name="note", invoke_without_command=True)
    @commands.has_permissions(kick_members=True)
    @commands.guild_only()
    async def note(self, ctx: commands.Context) -> None:
        """Staff notes on a member."""
        await send_command_browser(ctx, ctx.command)

    @note.command(name="add")
    @commands.has_permissions(kick_members=True)
    async def note_add(self, ctx, member: discord.Member, *, text: str) -> None:
        """Record a private note on a member."""
        case_id = await service.add_case(ctx.guild.id, member.id, ctx.author.id, "note", text)
        await ctx.send(embed=embeds.success(f"Note added on **{member}** (case #{case_id})."))

    @note.command(name="list")
    @commands.has_permissions(kick_members=True)
    async def note_list(self, ctx, member: discord.Member) -> None:
        """Show a member's notes."""
        rows = await service.list_notes(ctx.guild.id, member.id)
        if not rows:
            await ctx.send(embed=embeds.info(f"**{member}** has no notes."))
            return
        lines = [
            f"`#{c.id}` {c.reason or 'No reason'} · by <@{c.moderator_id}> · {discord.utils.format_dt(c.created_at, 'R')}"
            for c in rows
        ]
        await ctx.send(embed=embeds.info("\n".join(lines), f"{member.display_name}'s Notes ({len(rows)})"))

    @note.command(name="remove", aliases=["del"])
    @commands.has_permissions(kick_members=True)
    async def note_remove(self, ctx, case_id: int) -> None:
        """Remove a case by id."""
        if not await service.delete_case(ctx.guild.id, case_id):
            raise service.ModerationError("No case with that id in this server.")
        await ctx.send(embed=embeds.success(f"Removed case #{case_id}."))

    @commands.command(name="modlogs", aliases=["cases"])
    @commands.has_permissions(kick_members=True)
    @commands.guild_only()
    async def modlogs(self, ctx, member: discord.Member, page: int = 1) -> None:
        """Full moderation history for a member (every case type)."""
        page = max(1, page)
        per = 15
        rows, total = await service.list_cases(ctx.guild.id, member.id, limit=per, offset=(page - 1) * per)
        if not rows:
            await ctx.send(embed=embeds.info(f"**{member}** has no moderation history."))
            return
        lines = [
            f"`#{c.id}` **{c.kind}** · {c.reason or 'No reason'} · by <@{c.moderator_id}> · "
            f"{discord.utils.format_dt(c.created_at, 'R')}"
            for c in rows
        ]
        pages = (total + per - 1) // per
        e = embeds.info("\n".join(lines), f"{member.display_name}'s History ({total})")
        e.set_footer(text=f"Page {page}/{pages}")
        await ctx.send(embed=e)

    @commands.command(name="reason", extras={"example": "reason 12 raiding the server"})
    @commands.has_permissions(kick_members=True)
    @commands.guild_only()
    async def reason(self, ctx, case_id: int, *, reason: str) -> None:
        """Edit the reason on an existing case by its id."""
        if not await service.edit_case_reason(ctx.guild.id, case_id, reason):
            raise service.ModerationError("No case with that id in this server.")
        await ctx.send(embed=embeds.success(f"Updated the reason for case #{case_id}."))

    # ── immune ────────────────────────────────────────────────────────────────

    @commands.group(name="immune", invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def immune(self, ctx: commands.Context) -> None:
        """Protect a member or role from moderation actions."""
        await send_command_browser(ctx, ctx.command)

    @immune.command(name="add")
    @commands.has_permissions(manage_guild=True)
    async def immune_add(self, ctx, *, target: discord.Member | discord.Role) -> None:
        """Add a member or role to the immune list."""
        await service.add_immune(ctx.guild.id, target.id, isinstance(target, discord.Role))
        await ctx.send(embed=embeds.success(f"Added {target.mention} to the immune list."))

    @immune.command(name="remove")
    @commands.has_permissions(manage_guild=True)
    async def immune_remove(self, ctx, *, target: discord.Member | discord.Role) -> None:
        """Remove a member or role from the immune list."""
        if not await service.remove_immune(ctx.guild.id, target.id):
            await ctx.send(embed=embeds.error("That isn't on the immune list."))
            return
        await ctx.send(embed=embeds.success(f"Removed {target.mention} from the immune list."))

    @immune.command(name="list")
    @commands.has_permissions(manage_guild=True)
    async def immune_list(self, ctx: commands.Context) -> None:
        """Show the immune list."""
        rows = await service.list_immune(ctx.guild.id)
        if not rows:
            await ctx.send(embed=embeds.info("The immune list is empty."))
            return
        lines = [(f"<@&{tid}>" if is_role else f"<@{tid}>") for tid, is_role in rows]
        await ctx.send(embed=embeds.info("\n".join(lines), f"Immune ({len(rows)})"))

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
        await self._log(ctx.guild.id, action_embed("Lock", ctx.author, ctx.author, f"#{ctx.channel}"))

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
        await self._log(ctx.guild.id, action_embed("Unlock", ctx.author, ctx.author, f"#{ctx.channel}"))

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

    # ── role helpers ────────────────────────────────────────────────────────────

    def _check_role(self, ctx: commands.Context, role: discord.Role) -> None:
        if role >= ctx.guild.me.top_role:
            raise service.ModerationError("That role is above my highest role.")
        if ctx.author.id != ctx.guild.owner_id and role >= ctx.author.top_role:
            raise service.ModerationError("That role is above your highest role.")
        if role.managed:
            raise service.ModerationError("That role is managed by an integration.")

    async def _confirm(self, ctx: commands.Context, prompt: str) -> bool:
        msg = await ctx.send(embed=embeds.warning(f"{prompt} Reply `yes` to confirm."))

        def check(m: discord.Message) -> bool:
            return (
                m.author == ctx.author
                and m.channel == ctx.channel
                and m.content.lower() == "yes"
            )

        try:
            await self.bot.wait_for("message", check=check, timeout=30)
            return True
        except TimeoutError:
            await msg.edit(embed=embeds.info("Cancelled."))
            return False

    async def _purge(self, ctx, amount, *, check=lambda m: True, before=None, after=None) -> None:
        if amount < 1 or amount > 1000:
            raise service.ModerationError("Amount must be between 1 and 1000.")
        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass
        deleted = await ctx.channel.purge(limit=amount, check=check, before=before, after=after)
        note = await ctx.send(embed=embeds.success(f"Deleted {len(deleted)} message(s)."))
        await note.delete(delay=5)

    # ── role ────────────────────────────────────────────────────────────────────

    @commands.group(name="role", invoke_without_command=True)
    @commands.guild_only()
    async def role(self, ctx: commands.Context) -> None:
        """Role management. Bare command lists the subcommands."""
        await send_command_browser(ctx, ctx.command)

    @role.command(name="give", aliases=["add"])
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def role_give(self, ctx, member: discord.Member, *, role: discord.Role) -> None:
        """Add a role to a member."""
        self._check_role(ctx, role)
        if role in member.roles:
            raise service.ModerationError(f"{member} already has {role.mention}.")
        await member.add_roles(role, reason=f"role give by {ctx.author}")
        await ctx.send(embed=embeds.success(f"Gave {role.mention} to {member.mention}."))

    @role.command(name="take")
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def role_take(self, ctx, member: discord.Member, *, role: discord.Role) -> None:
        """Remove a role from a member."""
        self._check_role(ctx, role)
        if role not in member.roles:
            raise service.ModerationError(f"{member} doesn't have {role.mention}.")
        await member.remove_roles(role, reason=f"role take by {ctx.author}")
        await ctx.send(embed=embeds.success(f"Took {role.mention} from {member.mention}."))

    @role.command(name="create", aliases=["make"])
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def role_create(self, ctx, name: str, color: str | None = None) -> None:
        """Create a role. Quote multi-word names."""
        kwargs = {"name": name, "reason": f"role create by {ctx.author}"}
        if color:
            try:
                kwargs["color"] = discord.Color.from_str(color)
            except ValueError:
                raise service.ModerationError("Color must be a hex like `#5865f2`.") from None
        new = await ctx.guild.create_role(**kwargs)
        await ctx.send(embed=embeds.success(f"Created {new.mention}."))

    @role.command(name="delete", aliases=["del"])
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def role_delete(self, ctx, *, role: discord.Role) -> None:
        """Delete a role."""
        self._check_role(ctx, role)
        name = role.name
        await role.delete(reason=f"role delete by {ctx.author}")
        await ctx.send(embed=embeds.success(f"Deleted the role **{name}**."))

    @role.command(name="rename", aliases=["name"])
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def role_rename(self, ctx, role: discord.Role, *, name: str) -> None:
        """Rename a role."""
        self._check_role(ctx, role)
        await role.edit(name=name, reason=f"role rename by {ctx.author}")
        await ctx.send(embed=embeds.success(f"Renamed the role to **{name}**."))

    @role.command(name="color", aliases=["colour"])
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def role_color(self, ctx, role: discord.Role, color: str) -> None:
        """Change a role's color (hex)."""
        self._check_role(ctx, role)
        try:
            c = discord.Color.from_str(color)
        except ValueError:
            raise service.ModerationError("Color must be a hex like `#5865f2`.") from None
        await role.edit(color=c, reason=f"role color by {ctx.author}")
        await ctx.send(embed=embeds.success(f"Recolored {role.mention}."))

    @role.command(name="hoist")
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def role_hoist(self, ctx, *, role: discord.Role) -> None:
        """Toggle whether a role shows in the sidebar."""
        self._check_role(ctx, role)
        new = not role.hoist
        await role.edit(hoist=new, reason=f"role hoist by {ctx.author}")
        await ctx.send(embed=embeds.success(
            f"{role.mention} is {'now shown' if new else 'no longer shown'} in the sidebar."
        ))

    @role.command(name="mentionable", aliases=["mention"])
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def role_mentionable(self, ctx, *, role: discord.Role) -> None:
        """Toggle whether a role can be pinged."""
        self._check_role(ctx, role)
        new = not role.mentionable
        await role.edit(mentionable=new, reason=f"role mentionable by {ctx.author}")
        await ctx.send(embed=embeds.success(
            f"{role.mention} is {'now' if new else 'no longer'} mentionable."
        ))

    @role.command(name="info")
    async def role_info(self, ctx, *, role: discord.Role) -> None:
        """Show details about a role. (No permission required.)"""
        e = embeds.info("", role.name)
        e.add_field(name="ID", value=str(role.id))
        e.add_field(name="Color", value=str(role.color))
        e.add_field(name="Members", value=str(len(role.members)))
        e.add_field(name="Hoisted", value="yes" if role.hoist else "no")
        e.add_field(name="Mentionable", value="yes" if role.mentionable else "no")
        e.add_field(name="Created", value=discord.utils.format_dt(role.created_at, "R"))
        await ctx.send(embed=e)

    @role.command(name="everyone")
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def role_everyone(self, ctx, *, role: discord.Role) -> None:
        """Add a role to every member."""
        self._check_role(ctx, role)
        prompt = f"Add {role.mention} to **every** member? This can take a while."
        if not await self._confirm(ctx, prompt):
            return
        added = 0
        for m in ctx.guild.members:
            if role not in m.roles:
                try:
                    await m.add_roles(role, reason=f"role everyone by {ctx.author}")
                    added += 1
                except discord.HTTPException:
                    continue
        await ctx.send(embed=embeds.success(f"Added {role.mention} to {added} member(s)."))

    @role.command(name="humans")
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def role_humans(self, ctx, *, role: discord.Role) -> None:
        """Add a role to every non-bot member."""
        self._check_role(ctx, role)
        prompt = f"Add {role.mention} to all humans? This can take a while."
        if not await self._confirm(ctx, prompt):
            return
        added = 0
        for m in ctx.guild.members:
            if not m.bot and role not in m.roles:
                try:
                    await m.add_roles(role, reason=f"role humans by {ctx.author}")
                    added += 1
                except discord.HTTPException:
                    continue
        await ctx.send(embed=embeds.success(f"Added {role.mention} to {added} member(s)."))

    @role.command(name="bots")
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def role_bots(self, ctx, *, role: discord.Role) -> None:
        """Add a role to every bot."""
        self._check_role(ctx, role)
        if not await self._confirm(ctx, f"Add {role.mention} to all bots?"):
            return
        added = 0
        for m in ctx.guild.members:
            if m.bot and role not in m.roles:
                try:
                    await m.add_roles(role, reason=f"role bots by {ctx.author}")
                    added += 1
                except discord.HTTPException:
                    continue
        await ctx.send(embed=embeds.success(f"Added {role.mention} to {added} bot(s)."))

    @role.command(name="has")
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def role_has(self, ctx, source: discord.Role, *, target: discord.Role) -> None:
        """Give everyone who has one role another role."""
        self._check_role(ctx, target)
        holders = list(source.members)
        prompt = f"Add {target.mention} to all {len(holders)} members with {source.mention}?"
        if not await self._confirm(ctx, prompt):
            return
        added = 0
        for m in holders:
            if target not in m.roles:
                try:
                    await m.add_roles(target, reason=f"role has by {ctx.author}")
                    added += 1
                except discord.HTTPException:
                    continue
        await ctx.send(embed=embeds.success(f"Added {target.mention} to {added} member(s)."))

    @role.command(name="strip")
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def role_strip(self, ctx, *, role: discord.Role) -> None:
        """Remove a role from everyone who has it."""
        self._check_role(ctx, role)
        holders = list(role.members)
        prompt = f"Remove {role.mention} from all {len(holders)} members who have it?"
        if not await self._confirm(ctx, prompt):
            return
        removed = 0
        for m in holders:
            try:
                await m.remove_roles(role, reason=f"role strip by {ctx.author}")
                removed += 1
            except discord.HTTPException:
                continue
        await ctx.send(embed=embeds.success(f"Removed {role.mention} from {removed} member(s)."))

    # ── temp roles ────────────────────────────────────────────────────────────

    @commands.group(name="temprole", aliases=["tr"], invoke_without_command=True)
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    @commands.guild_only()
    async def temprole(self, ctx, member: discord.Member = None, role: discord.Role = None, duration: str = None) -> None:
        """Give a role that lifts itself after a duration (max 1 year)."""
        if member is None or role is None or duration is None:
            await send_command_browser(ctx, ctx.command)
            return
        await self._guard(ctx, member)
        self._check_role(ctx, role)
        delta = service.parse_duration(duration, max_delta=timedelta(days=365))
        if role not in member.roles:
            await member.add_roles(role, reason=f"temprole by {ctx.author}")
        expires = datetime.now(UTC) + delta
        await service.add_temprole(ctx.guild.id, member.id, role.id, expires)
        await ctx.send(embed=embeds.success(f"Gave {role.mention} to {member.mention} for {duration}."))

    @temprole.command(name="list")
    @commands.has_permissions(manage_roles=True)
    async def temprole_list(self, ctx: commands.Context) -> None:
        """Show active temp roles."""
        rows = await service.list_temproles(ctx.guild.id)
        if not rows:
            await ctx.send(embed=embeds.info("No active temp roles."))
            return
        lines = [
            f"<@{t.user_id}> · <@&{t.role_id}> · expires {discord.utils.format_dt(t.expires_at, 'R')}"
            for t in rows
        ]
        await ctx.send(embed=embeds.info("\n".join(lines)[:4000], f"Temp Roles ({len(rows)})"))

    @temprole.command(name="remove")
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def temprole_remove(self, ctx, member: discord.Member, *, role: discord.Role) -> None:
        """Lift a temp role early."""
        self._check_role(ctx, role)
        removed = await service.remove_temprole(ctx.guild.id, member.id, role.id)
        if role in member.roles:
            try:
                await member.remove_roles(role, reason=f"temprole removed by {ctx.author}")
            except discord.HTTPException:
                pass
        if removed == 0 and role not in member.roles:
            await ctx.send(embed=embeds.info("No matching temp role."))
            return
        await ctx.send(embed=embeds.success(f"Removed {role.mention} from {member.mention}."))

    # ── nickname / cleanup / pins / newusers ────────────────────────────────────

    @commands.command(name="nickname", aliases=["nick"])
    @commands.has_permissions(manage_nicknames=True)
    @commands.bot_has_permissions(manage_nicknames=True)
    @commands.guild_only()
    async def nickname(
        self, ctx, member: discord.Member | None = None, *, name: str | None = None
    ) -> None:
        """Set a member's nickname, or omit the name to reset it."""
        if member is None:
            await ctx.send(embed=embeds.info("`,nickname @user [name]` (omit the name to reset)"))
            return
        check_target(ctx, member)
        await member.edit(nick=name, reason=f"nickname by {ctx.author}")
        if name:
            await ctx.send(embed=embeds.success(f"Set {member.mention}'s nickname to **{name}**."))
        else:
            await ctx.send(embed=embeds.success(f"Reset {member.mention}'s nickname."))

    @commands.command(name="cleanup")
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    @commands.guild_only()
    async def cleanup(self, ctx, amount: int = 100) -> None:
        """Remove recent bot messages and command invocations."""
        await self._purge(ctx, amount, check=lambda m: m.author.bot or m.content.startswith(","))

    @commands.command(name="pin")
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    @commands.guild_only()
    async def pin(self, ctx, message: discord.Message | None = None) -> None:
        """Pin a message: reply to it, or give its ID or link."""
        if message is None and ctx.message.reference:
            ref = ctx.message.reference
            message = ref.resolved if isinstance(ref.resolved, discord.Message) else \
                await ctx.channel.fetch_message(ref.message_id)
        if message is None:
            raise service.ModerationError("Reply to a message or give its ID to pin.")
        await message.pin(reason=f"Pinned by {ctx.author}")
        await ctx.send(embed=embeds.success("Pinned the message."))

    @commands.command(name="unpin")
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    @commands.guild_only()
    async def unpin(self, ctx, message: discord.Message | None = None) -> None:
        """Unpin a message: reply to it, or give its ID or link."""
        if message is None and ctx.message.reference:
            ref = ctx.message.reference
            message = ref.resolved if isinstance(ref.resolved, discord.Message) else \
                await ctx.channel.fetch_message(ref.message_id)
        if message is None:
            raise service.ModerationError("Reply to a message or give its ID to unpin.")
        await message.unpin(reason=f"Unpinned by {ctx.author}")
        await ctx.send(embed=embeds.success("Unpinned the message."))

    @commands.command(name="newusers", aliases=["newmembers"])
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def newusers(self, ctx, amount: int = 10) -> None:
        """List the newest members (raid / suspicious check). Max 100."""
        amount = max(1, min(amount, 100))
        members = sorted(
            (m for m in ctx.guild.members if m.joined_at),
            key=lambda m: m.joined_at, reverse=True,
        )[:amount]
        lines = [
            f"{m.mention} · joined {discord.utils.format_dt(m.joined_at, 'R')} · "
            f"created {discord.utils.format_dt(m.created_at, 'R')}"
            for m in members
        ]
        e = embeds.info("\n".join(lines)[:4000], f"Newest {len(members)} Members")
        await ctx.send(embed=e)

    # ── jail ────────────────────────────────────────────────────────────────────

    @commands.group(name="jail", invoke_without_command=True)
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    @commands.guild_only()
    async def jail(
        self, ctx, member: discord.Member | None = None, *, reason: str = _DEFAULT_REASON
    ) -> None:
        """Jail a member: strip their roles and apply the jail role."""
        if member is None:
            await send_command_browser(ctx, ctx.command)
            return
        await self._guard(ctx, member)
        role_id = await service.get_jail_role(ctx.guild.id)
        if role_id is None:
            raise service.ModerationError("No jail role set. Use `,jail role <role>` first.")
        jail_role = ctx.guild.get_role(role_id)
        if jail_role is None:
            raise service.ModerationError(
                "The jail role no longer exists. Set it again with `,jail role <role>`."
            )
        if await service.is_jailed(ctx.guild.id, member.id):
            raise service.ModerationError(
                f"**{member}** is already jailed. Use `,unjail` to release them first."
            )
        removed = [
            r for r in member.roles
            if r != ctx.guild.default_role and not r.managed and r < ctx.guild.me.top_role
        ]
        keep = [r for r in member.roles if r not in removed and r != ctx.guild.default_role]
        await member.edit(roles=keep + [jail_role], reason=f"{ctx.author} (jail): {reason}")
        await service.store_jailed(ctx.guild.id, member.id, [r.id for r in removed])
        await service.add_case(ctx.guild.id, member.id, ctx.author.id, "jail", reason)
        await ctx.send(embed=embeds.success(f"Jailed **{member}**."))
        await self._log(ctx.guild.id, action_embed("Jail", ctx.author, member, reason))

    @jail.command(name="role")
    @commands.has_permissions(manage_roles=True)
    async def jail_role(self, ctx, role: discord.Role) -> None:
        """Set the role used for jailing. Configure its channel permissions yourself."""
        await service.set_jail_role(ctx.guild.id, role.id)
        await ctx.send(embed=embeds.success(
            f"Jail role set to {role.mention}. Deny it from viewing "
            "channels except your jail channel."
        ))

    @jail.command(name="list")
    @commands.has_permissions(manage_roles=True)
    async def jail_list(self, ctx) -> None:
        """List currently jailed members."""
        ids = await service.jailed_members(ctx.guild.id)
        if not ids:
            await ctx.send(embed=embeds.info("No one is jailed."))
            return
        await ctx.send(embed=embeds.info(
            "\n".join(f"<@{uid}>" for uid in ids), f"Jailed ({len(ids)})"
        ))

    @commands.command(name="unjail")
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    @commands.guild_only()
    async def unjail(self, ctx, member: discord.Member, *, reason: str = _DEFAULT_REASON) -> None:
        """Release a jailed member and restore their roles."""
        prior = await service.release_jailed(ctx.guild.id, member.id)
        if prior is None:
            raise service.ModerationError("That member isn't jailed.")
        role_id = await service.get_jail_role(ctx.guild.id)
        jail_role = ctx.guild.get_role(role_id) if role_id else None
        restore = [
            r for r in (ctx.guild.get_role(rid) for rid in prior)
            if r and not r.managed and r < ctx.guild.me.top_role
        ]
        new_roles = [
            r for r in member.roles if r != jail_role and r != ctx.guild.default_role
        ] + restore
        await member.edit(
            roles=list(dict.fromkeys(new_roles)), reason=f"{ctx.author} (unjail): {reason}"
        )
        await service.add_case(ctx.guild.id, member.id, ctx.author.id, "unjail", reason)
        await ctx.send(embed=embeds.success(f"Released **{member}**."))
        await self._log(ctx.guild.id, action_embed("Unjail", ctx.author, member, reason))

    # ── lockdown ────────────────────────────────────────────────────────────────

    @commands.group(name="lockdown", invoke_without_command=True)
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    @commands.guild_only()
    async def lockdown(self, ctx) -> None:
        """Lock or unlock every channel at once."""
        await send_command_browser(ctx, ctx.command)

    @lockdown.command(name="all")
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def lockdown_all(self, ctx) -> None:
        """Stop @everyone sending in every text channel."""
        if not await self._confirm(ctx, "Lock **every** channel? This can take a while."):
            return
        locked = 0
        for channel in ctx.guild.text_channels:
            ow = channel.overwrites_for(ctx.guild.default_role)
            if ow.send_messages is False:
                continue
            ow.send_messages = False
            try:
                await channel.set_permissions(
                    ctx.guild.default_role, overwrite=ow, reason=f"lockdown by {ctx.author}"
                )
                locked += 1
            except discord.HTTPException:
                continue
        await ctx.send(embed=embeds.success(f"{Emojis.LOCK} Locked {locked} channel(s)."))
        await self._log(
            ctx.guild.id, action_embed("Lockdown", ctx.author, ctx.author, "all channels")
        )

    @lockdown.command(name="end", aliases=["lift"])
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def lockdown_end(self, ctx) -> None:
        """Lift the lockdown across every text channel."""
        if not await self._confirm(ctx, "Unlock **every** channel?"):
            return
        unlocked = 0
        for channel in ctx.guild.text_channels:
            ow = channel.overwrites_for(ctx.guild.default_role)
            if ow.send_messages is not False:
                continue
            ow.send_messages = None
            try:
                await channel.set_permissions(
                    ctx.guild.default_role, overwrite=ow, reason=f"lockdown end by {ctx.author}"
                )
                unlocked += 1
            except discord.HTTPException:
                continue
        await ctx.send(embed=embeds.success(f"{Emojis.UNLOCK} Unlocked {unlocked} channel(s)."))
        await self._log(
            ctx.guild.id, action_embed("Unlockdown", ctx.author, ctx.author, "all channels")
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Moderation(bot))
