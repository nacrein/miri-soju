"""Server audit logging: configurable per server, posts to a chosen channel."""

from __future__ import annotations

import logging

import discord
from discord.ext import commands

from src.core import embeds
from src.modules.serverlog import service

log = logging.getLogger(__name__)


class ServerLog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ── configuration ───────────────────────────────────────────────────────

    @commands.hybrid_group(name="serverlog")
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def serverlog(self, ctx: commands.Context) -> None:
        """Configure audit logging for this server."""
        if ctx.invoked_subcommand is None:
            await ctx.send(embed=embeds.info("Use `serverlog channel #channel` to set the log channel."))

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

    # ── passive event listeners ─────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        await service.log_event(self.bot, member.guild.id, service.join_embed(member), "join")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        await service.log_event(self.bot, member.guild.id, service.leave_embed(member), "leave")

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message) -> None:
        if message.guild is None or message.author.bot:
            return
        await service.log_event(
            self.bot, message.guild.id, service.message_delete_embed(message), "msg_delete"
        )

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:
        if before.guild is None or before.author.bot:
            return
        if before.content == after.content:
            return  # ignore embed-unfurl edits with no content change
        await service.log_event(
            self.bot, before.guild.id, service.message_edit_embed(before, after), "msg_edit"
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ServerLog(bot))
