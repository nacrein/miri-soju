"""Vanity rep: reward members who carry the server's vanity URL in their status.

PREREQUISITE: ``on_presence_update`` only fires with the **presence** privileged
intent enabled (alongside members). ``src/core/bot.py`` does not enable it, so this
module is inert until ``intents.presences = True`` is set there (and approved in the
dev portal above 100 guilds). The reconcile loop also no-ops without the intent so it
never strips roles from a blind presence cache.

The cog owns all Discord work and the in-memory fast path; the service owns the
config and the durable tracker mirror plus the grant/revoke set math.
"""

from __future__ import annotations

import asyncio
import logging

import discord
from discord.ext import commands, tasks

from src.core import embeds
from src.core.emojis import Emojis
from src.core.errors import BotError
from src.core.paginator import Paginator, paginate_lines, send_command_browser
from src.modules.serverlog.service import log_event
from src.modules.vanity import config, service
from src.modules.vanity.gate import has_vanity

log = logging.getLogger(__name__)

_DEFAULT_TEMPLATE = "{user} is repping **{vanity}**, thank you! 💜"


def _is_repping(member: discord.Member, code: str) -> bool:
    """Is this member online and carrying the vanity in their custom status?"""
    if member.status is discord.Status.offline:  # invisible reads as offline
        return False
    needle = code.lower()
    for activity in member.activities:
        if isinstance(activity, discord.CustomActivity) and activity.name:
            text = activity.name.lower()
            if f"discord.gg/{needle}" in text or f".gg/{needle}" in text:
                return True
    return False


class Vanity(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._repping: dict[int, set[int]] = {}                  # guild_id -> user_ids (fast path)
        self._pending: dict[tuple[int, int], asyncio.Task] = {}  # debounced revokes
        self._semaphores: dict[int, asyncio.Semaphore] = {}      # per-guild role-endpoint throttle
        self._hydrate_task: asyncio.Task | None = None
        self._reconcile_loop.start()

    async def cog_load(self) -> None:
        from src.core.setup_registry import SetupEntry, register_setup
        from src.modules.vanity.setup_view import VanitySetupView

        register_setup(SetupEntry(
            key="vanity", label="Vanity", emoji=Emojis.GEM,
            description="Reward members who rep the server's vanity URL in their status.",
            factory=lambda author_id, guild_id: VanitySetupView(author_id, guild_id),
        ))
        self._hydrate_task = asyncio.create_task(self._hydrate())

    def cog_unload(self) -> None:
        from src.core.setup_registry import unregister_setup

        self._reconcile_loop.cancel()
        if self._hydrate_task is not None:
            self._hydrate_task.cancel()
        for task in list(self._pending.values()):
            task.cancel()
        unregister_setup("vanity")

    # ── helpers ───────────────────────────────────────────────────────────────

    def _sem(self, guild_id: int) -> asyncio.Semaphore:
        sem = self._semaphores.get(guild_id)
        if sem is None:
            sem = asyncio.Semaphore(config.ROLE_CONCURRENCY)
            self._semaphores[guild_id] = sem
        return sem

    async def _hydrate(self) -> None:
        """Load the durable tracker mirror into the fast path once guilds are cached."""
        await self.bot.wait_until_ready()
        try:
            for guild in self.bot.guilds:
                cfg = await service.get_config(guild.id)
                if cfg is not None and cfg.enabled:
                    self._repping[guild.id] = await service.get_active_ids(guild.id)
        except Exception:
            log.exception("vanity hydrate failed")

    # ── presence path ─────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_presence_update(self, before: discord.Member, after: discord.Member) -> None:
        guild = after.guild
        cfg = await service.get_config(guild.id)         # cached; None/disabled exits
        if cfg is None or not cfg.enabled or cfg.role_id is None:
            return
        code = guild.vanity_url_code                      # None when no vanity / not L3
        if not code:
            return
        was, now = _is_repping(before, code), _is_repping(after, code)
        if was == now:
            return                                        # the overwhelming majority exit here
        if now:
            self._cancel_pending_revoke(guild.id, after.id)
            await self._grant(guild, after, cfg)
        else:
            self._schedule_revoke(guild, after, cfg, code)

    def _cancel_pending_revoke(self, guild_id: int, user_id: int) -> None:
        task = self._pending.pop((guild_id, user_id), None)
        if task is not None:
            task.cancel()

    def _schedule_revoke(self, guild, member, cfg, code) -> None:
        key = (guild.id, member.id)
        self._cancel_pending_revoke(*key)
        self._pending[key] = asyncio.create_task(
            self._revoke_after_grace(guild, member, cfg, code)
        )

    async def _revoke_after_grace(self, guild, member, cfg, code) -> None:
        key = (guild.id, member.id)
        try:
            await asyncio.sleep(config.REVOKE_GRACE_SECONDS)
            live = guild.get_member(member.id)
            if live is not None and _is_repping(live, code):
                return                                    # flicker — keep the role
            await self._revoke(guild, member, cfg)
        finally:
            # Only clear our own slot: a newer scheduled revoke may have replaced us.
            if self._pending.get(key) is asyncio.current_task():
                self._pending.pop(key, None)

    # ── grant / revoke ────────────────────────────────────────────────────────

    async def _grant(self, guild, member, cfg) -> None:
        role = guild.get_role(cfg.role_id)
        if role is None:
            return
        already_had = role in member.roles  # e.g. after a restart, or a reconcile re-grant
        async with self._sem(guild.id):
            if not already_had:
                try:
                    await member.add_roles(role, reason="vanity rep")
                except discord.HTTPException:
                    return
        self._repping.setdefault(guild.id, set()).add(member.id)
        await service.add_tracker(guild.id, member.id)
        if not already_had:  # only thank/log when we actually granted the role, not on every pass
            await self._announce(guild, member)
            await self._log(guild, member, granted=True)

    async def _revoke(self, guild, member, cfg) -> None:
        live = guild.get_member(member.id) or member
        role = guild.get_role(cfg.role_id) if cfg.role_id else None
        async with self._sem(guild.id):
            if role is not None and role in getattr(live, "roles", []):
                try:
                    await live.remove_roles(role, reason="vanity rep ended")
                except discord.HTTPException:
                    pass
        self._repping.get(guild.id, set()).discard(member.id)
        await service.remove_tracker(guild.id, member.id)
        await self._log(guild, member, granted=False)

    async def _announce(self, guild, member) -> None:
        cfg = await service.get_config(guild.id)
        if cfg is None or cfg.channel_id is None:
            return
        channel = guild.get_channel(cfg.channel_id)
        if channel is None:
            return
        template = cfg.message_template or _DEFAULT_TEMPLATE
        text = (template
                .replace("{user}", member.mention)
                .replace("{vanity}", guild.vanity_url_code or ""))
        mentions = discord.AllowedMentions(users=True, roles=False, everyone=False)
        try:
            await channel.send(text, allowed_mentions=mentions)
        except discord.HTTPException:
            pass

    async def _log(self, guild, member, *, granted: bool) -> None:
        title = "Vanity rep started" if granted else "Vanity rep ended"
        desc = (f"{member.mention} {'now has' if granted else 'no longer has'} the vanity role.")
        try:
            await log_event(self.bot, guild.id, embeds.info(desc, f"{Emojis.GEM} {title}"), "mod")
        except discord.HTTPException:
            pass

    # ── reconcile backstop ────────────────────────────────────────────────────

    @tasks.loop(minutes=config.RECONCILE_INTERVAL_MINUTES)
    async def _reconcile_loop(self) -> None:
        if not self.bot.intents.presences:
            return  # inert without the presence intent — never strip on a blind cache
        for guild in list(self.bot.guilds):
            try:
                await self._reconcile_guild(guild)
            except Exception:
                log.exception("vanity reconcile failed for guild %s", guild.id)

    @_reconcile_loop.before_loop
    async def _before_reconcile(self) -> None:
        await self.bot.wait_until_ready()

    async def _reconcile_guild(self, guild: discord.Guild) -> None:
        cfg = await service.get_config(guild.id)
        if cfg is None or not cfg.enabled or cfg.role_id is None:
            return
        if not has_vanity(guild):
            await self._handle_lapse(guild, cfg)
            return
        code = guild.vanity_url_code
        if not code:
            return
        if not guild.chunked:
            return  # member cache is incomplete; reconciling now would mass-revoke real reppers
        live_ids = {m.id for m in guild.members if _is_repping(m, code)}
        to_grant, to_revoke = await service.reconcile_targets(guild.id, live_ids)
        self._repping[guild.id] = live_ids
        for uid in to_grant:
            member = guild.get_member(uid)
            if member is not None:
                await self._grant(guild, member, cfg)
        for uid in to_revoke:
            member = guild.get_member(uid)
            if member is not None:
                await self._revoke(guild, member, cfg)
            else:
                await service.remove_tracker(guild.id, uid)  # left the guild — just untrack

    async def _handle_lapse(self, guild: discord.Guild, cfg) -> None:
        """Vanity gone (boosts lapsed): strip the role from reppers and turn it off."""
        reppers = set(self._repping.get(guild.id, set())) | await service.get_active_ids(guild.id)
        role = guild.get_role(cfg.role_id) if cfg.role_id else None
        for uid in reppers:
            member = guild.get_member(uid)
            if member is not None and role is not None and role in member.roles:
                async with self._sem(guild.id):
                    try:
                        await member.remove_roles(role, reason="vanity lapsed")
                    except discord.HTTPException:
                        pass
        await service.clear_trackers(guild.id)
        self._repping.pop(guild.id, None)
        await service.set_enabled(guild.id, False)
        note = embeds.warning(
            "The vanity URL is no longer available (boosts lapsed): vanity rep was "
            "turned off and the role removed.",
            f"{Emojis.WARNING} Vanity disabled",
        )
        try:
            await log_event(self.bot, guild.id, note, "mod")
        except discord.HTTPException:
            pass

    # ── commands ──────────────────────────────────────────────────────────────

    async def cog_check(self, ctx: commands.Context) -> bool:
        if ctx.guild is None:
            raise commands.NoPrivateMessage()
        if not ctx.author.guild_permissions.manage_guild:
            raise commands.MissingPermissions(["manage_guild"])
        return True

    @commands.group(name="vanity", invoke_without_command=True)
    @commands.guild_only()
    async def vanity(self, ctx: commands.Context) -> None:
        """Reward members who rep the server's vanity URL in their custom status."""
        await send_command_browser(ctx, ctx.command)

    @vanity.command(name="enable")
    @commands.guild_only()
    async def vanity_enable(self, ctx: commands.Context) -> None:
        """Turn vanity rep on (needs a Boost Level 3 / Partner vanity URL)."""
        if not has_vanity(ctx.guild):
            raise BotError(
                "Discord grants a vanity URL at Boost Level 3 or with Partner/Verified status."
            )
        await service.set_enabled(ctx.guild.id, True)
        self._repping[ctx.guild.id] = await service.get_active_ids(ctx.guild.id)
        cfg = await service.get_config(ctx.guild.id)
        extra = "" if (cfg and cfg.role_id) else " Set a reward role with `,vanity role <role>`."
        intent = "" if self.bot.intents.presences else (
            " ⚠️ The bot's **presence intent** is off, so it can't see statuses yet."
        )
        await ctx.send(embed=embeds.success(f"Vanity rep enabled.{extra}{intent}"))

    @vanity.command(name="disable")
    @commands.guild_only()
    async def vanity_disable(self, ctx: commands.Context) -> None:
        """Turn vanity rep off (existing roles stay until removed)."""
        await service.set_enabled(ctx.guild.id, False)
        await ctx.send(embed=embeds.success("Vanity rep disabled."))

    @vanity.command(name="role")
    @commands.guild_only()
    async def vanity_role(self, ctx: commands.Context, *, role: discord.Role) -> None:
        """Set the role granted to members repping the vanity."""
        if role >= ctx.guild.me.top_role:
            raise BotError("That role is above my highest role, so I can't manage it.")
        await service.set_role(ctx.guild.id, role.id)
        await ctx.send(embed=embeds.success(f"Vanity reward role set to {role.mention}."))

    @vanity.command(name="channel")
    @commands.guild_only()
    async def vanity_channel(self, ctx: commands.Context, *, channel: discord.TextChannel) -> None:
        """Set the channel for thank-you messages."""
        await service.set_channel(ctx.guild.id, channel.id)
        await ctx.send(embed=embeds.success(f"Thank-you messages will post in {channel.mention}."))

    @vanity.command(name="message")
    @commands.guild_only()
    async def vanity_message(self, ctx: commands.Context, *, template: str) -> None:
        """Set the thank-you template. Placeholders: {user} {vanity}."""
        await service.set_message(ctx.guild.id, template[:500])
        await ctx.send(embed=embeds.success("Thank-you message updated."))

    @vanity.command(name="status")
    @commands.guild_only()
    async def vanity_status(self, ctx: commands.Context) -> None:
        """Show config plus the active rep count."""
        cfg = await service.get_config(ctx.guild.id)
        count = await service.active_count(ctx.guild.id)
        role = ctx.guild.get_role(cfg.role_id) if (cfg and cfg.role_id) else None
        channel = ctx.guild.get_channel(cfg.channel_id) if (cfg and cfg.channel_id) else None
        e = embeds.info("", f"{Emojis.GEM} Vanity Rep")
        code = ctx.guild.vanity_url_code
        e.add_field(name="Status", value="On" if (cfg and cfg.enabled) else "Off")
        e.add_field(name="Vanity URL", value=f"`.gg/{code}`" if code else "None")
        e.add_field(name="Reward role", value=role.mention if role else "Not set")
        e.add_field(name="Announce channel", value=channel.mention if channel else "Not set")
        e.add_field(name="Currently repping", value=str(count))
        if not self.bot.intents.presences:
            e.add_field(
                name="⚠️ Presence intent",
                value="Off. The bot can't read statuses yet.", inline=False,
            )
        await ctx.send(embed=e)

    @vanity.command(name="list")
    @commands.guild_only()
    async def vanity_list(self, ctx: commands.Context) -> None:
        """List the members currently repping the vanity."""
        ids = sorted(await service.get_active_ids(ctx.guild.id))
        if not ids:
            await ctx.send(embed=embeds.info("Nobody is repping the vanity right now."))
            return
        lines = [f"<@{uid}>" for uid in ids]
        pages = paginate_lines(lines, f"{Emojis.GEM} Repping the vanity ({len(ids)})")
        await Paginator(ctx.author.id, pages).start(ctx)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Vanity(bot))
