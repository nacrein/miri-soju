"""Leveling: the levels config tree, rank, the message listener, and voice time."""

from __future__ import annotations

import logging
import time

import discord
from discord.ext import commands, tasks

from src.core import embeds, rankings
from src.core.emojis import Emojis
from src.core.paginator import send_command_browser
from src.modules.leveling import config, service
from src.modules.leveling.voice import VoiceTracker

log = logging.getLogger(__name__)


class Leveling(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._voice = VoiceTracker()
        self._flush_voice.start()

    async def cog_load(self) -> None:
        # Register the ,setup levels panel. Deferred imports keep the registry (core)
        # free of any feature dependency.
        from src.core.setup_registry import SetupEntry, register_setup
        from src.modules.leveling.setup_view import LevelingSetupView

        register_setup(SetupEntry(
            key="levels", label="Leveling", emoji=Emojis.XP,
            description="XP per message, level-ups, and the announce channel.",
            factory=lambda author_id, guild_id: LevelingSetupView(author_id, guild_id),
        ))

    def cog_unload(self) -> None:
        from src.core.setup_registry import unregister_setup

        self._flush_voice.cancel()
        unregister_setup("levels")

    # ── shared ────────────────────────────────────────────────────────────────

    async def _confirm(self, ctx, prompt: str) -> bool:
        msg = await ctx.send(embed=embeds.warning(f"{prompt} Reply `yes` to confirm."))

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel and m.content.lower() == "yes"

        try:
            await self.bot.wait_for("message", check=check, timeout=30)
            return True
        except TimeoutError:
            await msg.edit(embed=embeds.info("Cancelled."))
            return False

    async def _grant_rewards(self, guild: discord.Guild, member: discord.Member, level: int) -> None:
        for lvl, role_id in await service.rewards_up_to(guild.id, level):
            role = guild.get_role(role_id)
            if role is not None and role not in member.roles and role < guild.me.top_role:
                try:
                    await member.add_roles(role, reason=f"level {lvl} reward")
                except discord.HTTPException:
                    pass

    async def _announce(self, guild, member, level, fallback) -> None:
        cfg = await service.get_config(guild.id)
        if cfg is None:
            return
        await self._grant_rewards(guild, member, level)
        text = service.render_message(cfg.level_up_message, member, level, guild)
        mentions = discord.AllowedMentions(users=True, everyone=False, roles=False)
        if cfg.announce_mode == "dm":
            try:
                await member.send(text)
            except discord.HTTPException:
                pass
            return
        if cfg.announce_mode == "channel":
            target = guild.get_channel(cfg.announce_channel_id) or fallback
        else:
            target = fallback
        if target is not None:
            try:
                await target.send(text, allowed_mentions=mentions)
            except discord.HTTPException:
                pass

    # ── member-facing ─────────────────────────────────────────────────────────

    @commands.hybrid_command(name="rank", aliases=["level", "lvl", "xp"])
    @commands.guild_only()
    async def rank(self, ctx, member: discord.Member | None = None) -> None:
        """Show your level, rank, and progress to the next level."""
        target = member or ctx.author
        if target.bot:
            raise commands.BadArgument("Bots don't earn XP.")
        p = await service.get_progress(ctx.guild.id, target.id)
        e = embeds.info("", f"{Emojis.RANK} {target.display_name}")
        e.add_field(name="Level", value=str(p["level"]))
        e.add_field(name="Rank", value=f"#{p['rank']}" if p["rank"] else "Unranked")
        e.add_field(name="XP", value=f"{p['into']:,} / {p['needed']:,}")
        e.add_field(name="Progress", value=self._bar(p["into"], p["needed"]), inline=False)
        if p["voice_minutes"]:
            e.add_field(name="Voice", value=f"{p['voice_minutes'] // 60}h {p['voice_minutes'] % 60}m")
        await ctx.send(embed=e)

    @staticmethod
    def _bar(into: int, needed: int, width: int = 20) -> str:
        if needed <= 0:
            return "▰" * width
        filled = min(width, int(width * into / needed))
        return "▰" * filled + "▱" * (width - filled)

    @commands.hybrid_command(name="top", aliases=["toplevels", "levels_top"])
    @commands.guild_only()
    async def top(self, ctx) -> None:
        """This server's level leaderboard (levels are per-server)."""
        rows = await service.leaderboard_level(ctx.guild.id, 10)
        entries = [(uid, f"Level {lvl}") for uid, lvl in rows]
        await ctx.send(embed=rankings.ranked_list(
            ctx.guild, entries, "Server Levels", author=ctx.author,
            footer=f"This server only · {ctx.clean_prefix}rank for your card",
            empty="No ranked members yet.",
        ))

    @commands.hybrid_command(name="voicetop", aliases=["vtop", "topvoice", "voiceleaderboard"])
    @commands.guild_only()
    async def voicetop(self, ctx) -> None:
        """Global voice-time leaderboard — top talkers across every server Miri is in."""
        entries = await service.leaderboard_voice_global(10)
        await ctx.send(embed=rankings.ranked_list(
            ctx.guild, entries, "Voice Time", author=ctx.author,
            footer="Global · across every server",
            empty="No voice time tracked yet.",
        ))

    # ── admin config (manage_guild on every subcommand) ────────────────────────

    @commands.group(name="levels", invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def levels(self, ctx) -> None:
        """Leveling settings for this server."""
        await send_command_browser(ctx, ctx.command)

    @levels.command(name="settings", aliases=["config"])
    @commands.has_permissions(manage_guild=True)
    async def levels_settings(self, ctx) -> None:
        """Show this server's current leveling configuration."""
        cfg = await service.get_config(ctx.guild.id)
        if cfg is None or not cfg.enabled:
            await ctx.send(embed=embeds.info("Leveling is off. `,levels enable` to start."))
            return
        where = {"here": "where the member is active", "dm": "by DM",
                 "channel": f"<#{cfg.announce_channel_id}>"}.get(cfg.announce_mode, "where active")
        e = embeds.info("", "Leveling Settings")
        e.add_field(name="Status", value="on")
        e.add_field(name="XP / message", value=str(cfg.xp_per_message))
        e.add_field(name="Cooldown", value=f"{cfg.message_cooldown}s")
        e.add_field(name="Announce", value=where, inline=False)
        e.add_field(name="Message", value=cfg.level_up_message, inline=False)
        rewards = await service.list_rewards(ctx.guild.id)
        multipliers = await service.list_multipliers(ctx.guild.id)
        e.add_field(name="Rewards", value=str(len(rewards)))
        e.add_field(name="Multipliers", value=str(len(multipliers)))
        await ctx.send(embed=e)

    @levels.command(name="enable")
    @commands.has_permissions(manage_guild=True)
    async def levels_enable(self, ctx) -> None:
        """Turn leveling on."""
        await service.set_enabled(ctx.guild.id, True)
        await ctx.send(embed=embeds.success("Leveling enabled."))

    @levels.command(name="disable")
    @commands.has_permissions(manage_guild=True)
    async def levels_disable(self, ctx) -> None:
        """Turn leveling off."""
        await service.set_enabled(ctx.guild.id, False)
        await ctx.send(embed=embeds.success("Leveling disabled."))

    @levels.command(name="rate")
    @commands.has_permissions(manage_guild=True)
    async def levels_rate(self, ctx, amount: int) -> None:
        """Set XP awarded per message (1-1000)."""
        if amount < config.RATE_MIN or amount > config.RATE_MAX:
            raise commands.BadArgument(
                f"Rate must be between {config.RATE_MIN} and {config.RATE_MAX}."
            )
        await service.set_rate(ctx.guild.id, amount)
        await ctx.send(embed=embeds.success(f"XP per message set to {amount}."))

    @levels.command(name="cooldown")
    @commands.has_permissions(manage_guild=True)
    async def levels_cooldown(self, ctx, seconds: int) -> None:
        """Set the gap between XP-earning messages (0-3600s)."""
        if seconds < config.COOLDOWN_MIN or seconds > config.COOLDOWN_MAX:
            raise commands.BadArgument(
                f"Cooldown must be between {config.COOLDOWN_MIN} and {config.COOLDOWN_MAX} seconds."
            )
        await service.set_cooldown(ctx.guild.id, seconds)
        await ctx.send(embed=embeds.success(f"Message cooldown set to {seconds}s."))

    @levels.command(name="channel")
    @commands.has_permissions(manage_guild=True)
    async def levels_channel(self, ctx, *, target: str) -> None:
        """Where level-ups post: `here`, `dm`, or a channel."""
        t = target.strip().lower()
        if t == "here":
            await service.set_channel(ctx.guild.id, "here", None)
            await ctx.send(embed=embeds.success("Level-ups will post where the member is active."))
        elif t == "dm":
            await service.set_channel(ctx.guild.id, "dm", None)
            await ctx.send(embed=embeds.success("Level-ups will be sent by DM."))
        else:
            try:
                channel = await commands.TextChannelConverter().convert(ctx, target)
            except commands.BadArgument:
                raise commands.BadArgument("Give `here`, `dm`, or a channel.") from None
            await service.set_channel(ctx.guild.id, "channel", channel.id)
            await ctx.send(embed=embeds.success(f"Level-ups will post in {channel.mention}."))

    @levels.command(name="message")
    @commands.has_permissions(manage_guild=True)
    async def levels_message(self, ctx, *, text: str) -> None:
        """Set the level-up message. Placeholders: {user} {user.name} {level} {server}."""
        await service.set_message(ctx.guild.id, text)
        await ctx.send(embed=embeds.success("Level-up message updated."))

    @levels.command(name="setlevel")
    @commands.has_permissions(manage_guild=True)
    async def levels_setlevel(self, ctx, member: discord.Member, level: int) -> None:
        """Force a member's level (0-1000)."""
        if level < 0 or level > 1000:
            raise commands.BadArgument("Level must be between 0 and 1000.")
        await service.set_level(ctx.guild.id, member.id, level)
        await ctx.send(embed=embeds.success(f"Set {member.mention} to level {level}."))

    @levels.command(name="reset")
    @commands.has_permissions(manage_guild=True)
    async def levels_reset(self, ctx, member: discord.Member) -> None:
        """Wipe one member's progress."""
        await service.reset_member(ctx.guild.id, member.id)
        await ctx.send(embed=embeds.success(f"Reset {member.mention}'s progress."))

    @levels.command(name="resetall")
    @commands.has_permissions(manage_guild=True)
    async def levels_resetall(self, ctx) -> None:
        """Wipe every member's progress in this server."""
        if not await self._confirm(ctx, "Reset **all** leveling progress in this server?"):
            return
        count = await service.reset_all(ctx.guild.id)
        await ctx.send(embed=embeds.success(f"Reset {count} member(s)."))

    # ── rewards subgroup ──────────────────────────────────────────────────────

    @levels.group(name="reward", invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def levels_reward(self, ctx) -> None:
        """Roles granted on reaching a level."""
        await self._show_rewards(ctx)

    @levels_reward.command(name="add")
    @commands.has_permissions(manage_guild=True)
    async def reward_add(self, ctx, level: int, *, role: discord.Role) -> None:
        """Grant a role when members reach a level."""
        if role >= ctx.guild.me.top_role:
            raise commands.BadArgument("That role is above my highest role.")
        await service.add_reward(ctx.guild.id, level, role.id)
        await ctx.send(embed=embeds.success(f"Members reaching level {level} now get {role.mention}."))

    @levels_reward.command(name="remove")
    @commands.has_permissions(manage_guild=True)
    async def reward_remove(self, ctx, level: int) -> None:
        """Remove a level's reward."""
        if not await service.remove_reward(ctx.guild.id, level):
            raise commands.BadArgument("No reward at that level.")
        await ctx.send(embed=embeds.success(f"Removed the level {level} reward."))

    async def _show_rewards(self, ctx) -> None:
        rows = await service.list_rewards(ctx.guild.id)
        if not rows:
            await ctx.send(embed=embeds.info("No level rewards. `,levels reward add <level> <role>`"))
            return
        lines = [f"Level {lvl} → <@&{rid}>" for lvl, rid in rows]
        await ctx.send(embed=embeds.info("\n".join(lines), "Level Rewards"))

    # ── multipliers subgroup ──────────────────────────────────────────────────

    @levels.group(name="multiplier", aliases=["mult"], invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def levels_multiplier(self, ctx) -> None:
        """Per-channel XP multipliers."""
        await self._show_multipliers(ctx)

    @levels_multiplier.command(name="set")
    @commands.has_permissions(manage_guild=True)
    async def mult_set(self, ctx, channel: discord.abc.GuildChannel, rate: float) -> None:
        """Scale XP in a channel (0-10; 0 disables XP there). Works for text and voice."""
        if rate < 0 or rate > 10:
            raise commands.BadArgument("Rate must be between 0 and 10.")
        # Only text/voice channel ids ever match an XP lookup; a category/stage/forum
        # id would store a row that silently never applies, so reject it up front.
        if not isinstance(channel, discord.TextChannel | discord.VoiceChannel):
            raise commands.BadArgument("Pick a text or voice channel (not a category).")
        await service.set_multiplier(ctx.guild.id, channel.id, rate)
        await ctx.send(embed=embeds.success(f"{channel.mention} now earns {rate}x XP."))

    @levels_multiplier.command(name="remove")
    @commands.has_permissions(manage_guild=True)
    async def mult_remove(self, ctx, channel: discord.abc.GuildChannel) -> None:
        """Remove a channel's multiplier."""
        if not await service.remove_multiplier(ctx.guild.id, channel.id):
            raise commands.BadArgument("That channel has no multiplier.")
        await ctx.send(embed=embeds.success(f"Removed {channel.mention}'s multiplier."))

    async def _show_multipliers(self, ctx) -> None:
        rows = await service.list_multipliers(ctx.guild.id)
        if not rows:
            await ctx.send(embed=embeds.info("No channel multipliers. `,levels multiplier set <#channel> <rate>`"))
            return
        lines = [f"<#{cid}> → {m}x" for cid, m in rows]
        await ctx.send(embed=embeds.info("\n".join(lines), "Channel Multipliers"))

    # ── XP earning ────────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or message.guild is None:
            return
        level = await service.award_message_xp(message.guild.id, message.author.id, message.channel.id)
        if level is not None:
            await self._announce(message.guild, message.author, level, message.channel)

    def _eligible(self, member: discord.Member) -> bool:
        """Is this member actively present in voice right now? Not a bot, in a real
        (non-AFK) channel, not muted or deafened, and with at least one other human
        for company. Voice time accrues only while this holds."""
        vs = member.voice
        if member.bot or vs is None or vs.channel is None:
            return False
        if vs.channel == member.guild.afk_channel:
            return False
        if vs.self_mute or vs.mute or vs.self_deaf or vs.deaf:
            return False
        return sum(1 for m in vs.channel.members if not m.bot) >= 2

    @commands.Cog.listener()
    async def on_voice_state_update(
        self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState
    ) -> None:
        # Event-driven accrual: a member's join/leave/mute/deafen/move ends one
        # eligible interval and may start another — and, by changing a channel's
        # head-count, flips the 'alone' status of everyone else in the channels it
        # touched. Settle them all; the tracker banks whole minutes for the flush.
        if member.bot:
            return
        now = time.monotonic()
        key = (member.guild.id, member.id)
        if after.channel is None:
            self._voice.leave(key, now)
        else:
            self._voice.observe(key, after.channel.id, self._eligible(member), now)
        for channel in {before.channel, after.channel}:
            if channel is None:
                continue
            for other in channel.members:
                if other.bot or other.id == member.id:
                    continue
                self._voice.observe(
                    (member.guild.id, other.id), channel.id, self._eligible(other), now
                )

    @tasks.loop(seconds=60)
    async def _flush_voice(self) -> None:
        """Bank the in-progress intervals and write the accrued minutes in one
        batched transaction, then announce any level-ups."""
        self._voice.checkpoint(time.monotonic())
        batch = self._voice.drain()
        if not batch:
            return
        try:
            levelups = await service.credit_voice(batch)
        except Exception:
            log.exception("voice credit flush failed; re-queueing %d entries", len(batch))
            self._voice.restore(batch)
            return
        for guild_id, user_id, level in levelups:
            guild = self.bot.get_guild(guild_id)
            member = guild.get_member(user_id) if guild else None
            if guild and member:
                channel = member.voice.channel if member.voice else None
                await self._announce(guild, member, level, channel)

    @_flush_voice.before_loop
    async def _before_flush(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Leveling(bot))
