"""VoiceMaster: join a create channel, get a private voice channel you control.

The cog owns all Discord work (spawn/move/edit/delete) and the voice-state lifecycle;
the persistent panel (``views.VoicePanelView``) drives per-channel controls. Join
order is tracked in memory so ownership can pass to the next member when an owner
leaves. All ``,vm`` commands require manage_guild (via ``cog_check``).
"""

from __future__ import annotations

import asyncio
import logging

import discord
from discord.ext import commands

from src.core import embeds
from src.core.emojis import Emojis
from src.core.errors import BotError
from src.core.paginator import send_command_browser
from src.modules.voicemaster import service, state
from src.modules.voicemaster.views import VoicePanelView, panel_embed

log = logging.getLogger(__name__)


class Voicemaster(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._order: dict[int, list[int]] = {}  # channel_id -> member ids in join order
        self._sweep_task: asyncio.Task | None = None

    async def cog_load(self) -> None:
        from src.core.setup_registry import SetupEntry, register_setup
        from src.modules.voicemaster.setup_view import VoiceMasterSetupView

        register_setup(SetupEntry(
            key="voicemaster", label="VoiceMaster", emoji=Emojis.VOICE,
            description="Temporary, member-controlled voice channels via a button panel.",
            factory=lambda author_id, guild_id: VoiceMasterSetupView(author_id, guild_id),
        ))
        # Re-attach the persistent panel handlers (one shared view serves every guild's
        # panel message via its static custom_ids) and sweep crash-orphaned channels.
        self.bot.add_view(VoicePanelView())
        self._sweep_task = asyncio.create_task(self._orphan_sweep())

    def cog_unload(self) -> None:
        from src.core.setup_registry import unregister_setup

        if self._sweep_task is not None:
            self._sweep_task.cancel()
        unregister_setup("voicemaster")

    # ── startup sweep ──────────────────────────────────────────────────────────

    async def _orphan_sweep(self) -> None:
        await self.bot.wait_until_ready()
        try:
            for guild in self.bot.guilds:
                for record in await service.list_tracked(guild.id):
                    channel = guild.get_channel(record.channel_id)
                    if channel is None:
                        await service.delete_channel(guild.id, record.channel_id)  # row orphan
                    elif not any(not m.bot for m in channel.members):
                        await self._delete_channel(channel)  # empty leftover
                    else:
                        self._order[record.channel_id] = [
                            m.id for m in channel.members if not m.bot
                        ]
        except Exception:
            log.exception("VoiceMaster orphan sweep failed")

    # ── voice lifecycle ─────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_voice_state_update(
        self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState
    ) -> None:
        if member.bot:
            return
        before_id = before.channel.id if before.channel else None
        after_id = after.channel.id if after.channel else None
        if before.channel is not None and before_id != after_id:
            await self._handle_leave(member, before.channel)
        if after.channel is not None and after_id != before_id:
            await self._handle_join(member, after.channel)

    async def _handle_join(self, member: discord.Member, channel: discord.VoiceChannel) -> None:
        cfg = await service.get_config(member.guild.id)
        if cfg is None:
            return  # VM never configured here (cheap cached miss)
        record = await service.get_channel_by_id(member.guild.id, channel.id)
        if record is not None:  # joined a tracked channel — remember join order
            order = self._order.setdefault(channel.id, [])
            if member.id not in order:
                order.append(member.id)
            return
        if not cfg.enabled or cfg.create_channel_id is None or channel.id != cfg.create_channel_id:
            return
        if state.on_create_cooldown(member.guild.id, member.id):
            return
        await self._spawn(member, channel, cfg)

    async def _handle_leave(self, member: discord.Member, channel: discord.VoiceChannel) -> None:
        cfg = await service.get_config(member.guild.id)
        if cfg is None:
            return
        record = await service.get_channel_by_id(member.guild.id, channel.id)
        if record is None:
            return  # not a tracked channel
        order = self._order.get(channel.id)
        if order and member.id in order:
            order.remove(member.id)
        # Re-check membership right before acting, to dodge the leave/join race.
        live = member.guild.get_channel(channel.id)
        if live is None:
            await self._cleanup_record(member.guild.id, channel.id)
            return
        humans = [m for m in live.members if not m.bot]
        if not humans:
            await self._delete_channel(live)
            return
        if member.id == record.owner_id:  # owner left a still-occupied channel — pass it on
            next_id = self._next_owner(channel.id, humans)
            if next_id is not None:
                await service.transfer_ownership(member.guild.id, channel.id, next_id)

    def _next_owner(self, channel_id: int, humans: list[discord.Member]) -> int | None:
        present = {m.id for m in humans}
        for uid in self._order.get(channel_id, []):
            if uid in present:
                return uid
        return humans[0].id if humans else None

    async def _spawn(self, member: discord.Member, create_channel, cfg) -> None:
        state.mark_create(member.guild.id, member.id)
        overwrites = {
            member: discord.PermissionOverwrite(
                connect=True, manage_channels=True, move_members=True
            ),
        }
        try:
            new = await member.guild.create_voice_channel(
                name=f"{member.display_name}'s channel"[:100],
                category=create_channel.category,
                overwrites=overwrites,
                reason="VoiceMaster spawn",
            )
        except discord.HTTPException:
            log.warning("VoiceMaster: failed to create channel in guild %s", member.guild.id)
            return
        # Record the channel BEFORE moving the member in. move_to fires a voice event
        # dispatched as a separate task; _handle_leave/_handle_join must see the tracked
        # row, or a fast disconnect during the move leaves an orphaned empty channel.
        await service.create_channel(member.guild.id, member.id, new.id)
        self._order[new.id] = [member.id]
        try:
            await member.move_to(new, reason="VoiceMaster")
        except discord.HTTPException:
            try:
                await new.delete(reason="VoiceMaster spawn failed")
            except discord.HTTPException:
                pass
            await self._cleanup_record(member.guild.id, new.id)

    async def _delete_channel(self, channel) -> None:
        try:
            await channel.delete(reason="VoiceMaster empty")
        except discord.HTTPException:
            pass
        await self._cleanup_record(channel.guild.id, channel.id)

    async def _cleanup_record(self, guild_id: int, channel_id: int) -> None:
        await service.delete_channel(guild_id, channel_id)
        self._order.pop(channel_id, None)
        state.forget_channel(channel_id)

    # ── commands ────────────────────────────────────────────────────────────────

    async def cog_check(self, ctx: commands.Context) -> bool:
        if ctx.guild is None:
            raise commands.NoPrivateMessage()
        if not ctx.author.guild_permissions.manage_guild:
            raise commands.MissingPermissions(["manage_guild"])
        return True

    @commands.group(name="vm", aliases=["voicemaster"], invoke_without_command=True)
    @commands.guild_only()
    async def vm(self, ctx: commands.Context) -> None:
        """Temporary voice channels members control with a button panel."""
        await send_command_browser(ctx, ctx.command)

    @vm.command(name="setup")
    @commands.guild_only()
    async def vm_setup(
        self, ctx: commands.Context,
        create_channel: discord.VoiceChannel, panel_channel: discord.TextChannel,
    ) -> None:
        """Pick the create channel and post the control panel (also enables VoiceMaster)."""
        await service.set_create_channel(ctx.guild.id, create_channel.id)
        try:
            msg = await panel_channel.send(embed=panel_embed(), view=VoicePanelView())
        except discord.HTTPException:
            raise BotError("I couldn't post the panel there. Check my permissions.") from None
        await service.set_panel_message(ctx.guild.id, panel_channel.id, msg.id)
        await service.set_enabled(ctx.guild.id, True)
        await ctx.send(embed=embeds.success(
            f"VoiceMaster ready. Join {create_channel.mention} to spawn a channel. "
            f"Panel posted in {panel_channel.mention}.",
        ))

    @vm.command(name="enable")
    @commands.guild_only()
    async def vm_enable(self, ctx: commands.Context) -> None:
        """Turn VoiceMaster on."""
        cfg = await service.get_config(ctx.guild.id)
        if cfg is None or cfg.create_channel_id is None:
            raise BotError("Run `,vm setup` first to pick a create channel and post the panel.")
        await service.set_enabled(ctx.guild.id, True)
        await ctx.send(embed=embeds.success("VoiceMaster enabled."))

    @vm.command(name="disable")
    @commands.guild_only()
    async def vm_disable(self, ctx: commands.Context) -> None:
        """Turn VoiceMaster off (existing channels stay until they empty)."""
        await service.set_enabled(ctx.guild.id, False)
        await ctx.send(embed=embeds.success("VoiceMaster disabled."))

    @vm.command(name="reset")
    @commands.guild_only()
    async def vm_reset(self, ctx: commands.Context) -> None:
        """Delete all active VoiceMaster channels and reset the config."""
        removed = 0
        for record in await service.list_tracked(ctx.guild.id):
            channel = ctx.guild.get_channel(record.channel_id)
            if channel is not None:
                try:
                    await channel.delete(reason="VoiceMaster reset")
                except discord.HTTPException:
                    pass
            await service.delete_channel(ctx.guild.id, record.channel_id)
            self._order.pop(record.channel_id, None)
            removed += 1
        await service.reset_config(ctx.guild.id)
        await ctx.send(embed=embeds.success(
            f"VoiceMaster reset: removed {removed} channel(s) and cleared the config."
        ))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Voicemaster(bot))
