"""Server audit logging: configurable per server, posts to a chosen channel."""

from __future__ import annotations

import logging

import discord
from discord.ext import commands

from src.core import embeds
from src.core.emojis import Emojis
from src.core.paginator import send_command_browser
from src.modules.serverlog import service

log = logging.getLogger(__name__)


# ── event embed builders ────────────────────────────────────────────────────

def _truncate(text: str, limit: int = 1000) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def join_embed(member: discord.Member) -> discord.Embed:
    e = discord.Embed(
        description=f"{Emojis.JOIN} {member.mention} joined", color=discord.Color.green()
    )
    e.set_author(name=str(member), icon_url=member.display_avatar.url)
    e.add_field(name="Account created", value=discord.utils.format_dt(member.created_at, "R"))
    e.set_footer(text=f"ID: {member.id}")
    e.timestamp = discord.utils.utcnow()
    return e


def leave_embed(member: discord.Member) -> discord.Embed:
    e = discord.Embed(
        description=f"{Emojis.LEAVE} {member.mention} left", color=discord.Color.red()
    )
    e.set_author(name=str(member), icon_url=member.display_avatar.url)
    e.set_footer(text=f"ID: {member.id}")
    e.timestamp = discord.utils.utcnow()
    return e


def message_delete_embed(message: discord.Message) -> discord.Embed:
    e = discord.Embed(
        description=(
            f"{Emojis.MESSAGE_DELETE} Message by {message.author.mention} "
            f"deleted in {message.channel.mention}"
        ),
        color=discord.Color.orange(),
    )
    if message.content:
        e.add_field(name="Content", value=_truncate(message.content), inline=False)
    e.set_footer(text=f"Author ID: {message.author.id}")
    e.timestamp = discord.utils.utcnow()
    return e


def message_edit_embed(before: discord.Message, after: discord.Message) -> discord.Embed:
    # Tighter cap on edits: two fields plus the jump link must stay well under
    # Discord's 6000-char total embed limit.
    e = discord.Embed(
        description=(
            f"{Emojis.MESSAGE_EDIT} Message by {before.author.mention} "
            f"edited in {before.channel.mention}"
        ),
        color=discord.Color.blue(),
    )
    e.add_field(name="Before", value=_truncate(before.content, 900) or "(empty)", inline=False)
    e.add_field(name="After", value=_truncate(after.content, 900) or "(empty)", inline=False)
    e.add_field(name="Jump", value=f"[link]({after.jump_url})", inline=False)
    e.set_footer(text=f"Author ID: {before.author.id}")
    e.timestamp = discord.utils.utcnow()
    return e


class ServerLog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        from src.core.setup_registry import SetupEntry, register_setup
        from src.modules.serverlog.setup_view import ServerLogSetupView

        register_setup(SetupEntry(
            key="logging", label="Server Logging", emoji=Emojis.CHANNEL,
            description="The audit-log channel and which server events to log.",
            factory=lambda author_id, guild_id: ServerLogSetupView(author_id, guild_id),
        ))

    def cog_unload(self) -> None:
        from src.core.setup_registry import unregister_setup

        unregister_setup("logging")

    # ── configuration ───────────────────────────────────────────────────────

    @commands.hybrid_group(name="serverlog")
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def serverlog(self, ctx: commands.Context) -> None:
        """Configure audit logging for this server."""
        if ctx.invoked_subcommand is None:
            await send_command_browser(ctx, ctx.command)

    @serverlog.command(name="channel")
    async def set_channel(self, ctx: commands.Context, channel: discord.TextChannel) -> None:
        """Set the audit log channel (enables logging)."""
        await service.set_log_channel(ctx.guild.id, channel.id)
        await ctx.send(embed=embeds.success(f"Audit logs will be sent to {channel.mention}."))

    @serverlog.command(name="disable")
    async def disable(self, ctx: commands.Context) -> None:
        """Turn off all audit logging for this server."""
        await service.disable_logging(ctx.guild.id)
        await ctx.send(embed=embeds.success("Audit logging disabled."))

    @serverlog.command(name="toggle")
    async def toggle(self, ctx: commands.Context, event: str, on: bool) -> None:
        """Toggle an event: joins, leaves, deletes, edits, mod."""
        mapping = {
            "joins": "log_joins",
            "leaves": "log_leaves",
            "deletes": "log_message_delete",
            "edits": "log_message_edit",
            "mod": "log_mod_actions",
        }
        flag = mapping.get(event.lower())
        if flag is None:
            await ctx.send(embed=embeds.error(f"Unknown event. Choose: {', '.join(mapping)}."))
            return
        await service.set_event_flag(ctx.guild.id, flag, on)
        await ctx.send(embed=embeds.success(f"`{event}` logging set to `{on}`."))

    @serverlog.command(name="status")
    async def status(self, ctx: commands.Context) -> None:
        """Show this server's logging configuration."""
        s = await service.get_config_summary(ctx.guild.id)
        if not s["enabled"]:
            await ctx.send(embed=embeds.info(
                "Audit logging is off. Use `,serverlog channel #channel` to enable."
            ))
            return

        def onoff(v: bool) -> str:
            return "on" if v else "off"

        e = embeds.info("", "Server Log Settings")
        e.add_field(name="Channel", value=f"<#{s['channel_id']}>", inline=False)
        e.add_field(name="Joins", value=onoff(s["joins"]))
        e.add_field(name="Leaves", value=onoff(s["leaves"]))
        e.add_field(name="Deletes", value=onoff(s["deletes"]))
        e.add_field(name="Edits", value=onoff(s["edits"]))
        e.add_field(name="Mod actions", value=onoff(s["mod"]))
        await ctx.send(embed=e)

    # ── passive event listeners ─────────────────────────────────────────────

    async def _dispatch(self, guild_id: int, embed: discord.Embed, category: str) -> None:
        """Send the event embed to the guild's log channel if the category is on."""
        channel_id = await service.resolve_log_channel(guild_id, category)
        if channel_id is None:
            return
        channel = self.bot.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            return
        try:
            await channel.send(embed=embed)
        except discord.HTTPException:
            pass

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        await self._dispatch(member.guild.id, join_embed(member), "join")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        await self._dispatch(member.guild.id, leave_embed(member), "leave")

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message) -> None:
        if message.guild is None or message.author.bot:
            return
        await self._dispatch(message.guild.id, message_delete_embed(message), "msg_delete")

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:
        if before.guild is None or before.author.bot:
            return
        if before.content == after.content:
            return  # ignore embed-unfurl edits with no content change
        await self._dispatch(before.guild.id, message_edit_embed(before, after), "msg_edit")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ServerLog(bot))
