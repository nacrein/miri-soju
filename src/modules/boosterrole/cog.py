"""Booster roles: each server booster gets one custom role they create and style.

The module is built to survive boost lapses, role-list reordering, and manual role
deletion without leaving dangling state — the BoosterRole record persists name/color/
icon so a reboost can reconstruct a deleted role faithfully. The cog owns all Discord
work (create/edit/delete/reposition); the service owns the persisted records.
"""

from __future__ import annotations

import asyncio
import inspect
import logging

import discord
from discord.ext import commands, tasks

from src.core import embeds
from src.core.emojis import Emojis
from src.core.errors import BotError
from src.core.paginator import send_command_browser
from src.modules.boosterrole import config, service

log = logging.getLogger(__name__)

# Discord caps a guild at 250 roles — an external limit, guarded at ,br create.
_ROLE_CAP = 250

# Discord's holographic preset (primary, secondary, tertiary).
_HOLO = (11127295, 16759788, 16761760)


def _enhanced_colours_supported() -> bool:
    """Whether the installed discord.py exposes the secondary-colour role API."""
    try:
        return "secondary_colour" in inspect.signature(discord.Guild.create_role).parameters
    except (ValueError, TypeError):  # pragma: no cover - defensive
        return False


_ENHANCED = _enhanced_colours_supported()


def _has(guild: discord.Guild, feature: str) -> bool:
    return feature in guild.features


class Boosterrole(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._startup_task: asyncio.Task | None = None
        self._reconcile_loop.start()

    async def cog_load(self) -> None:
        from src.core.setup_registry import SetupEntry, register_setup
        from src.modules.boosterrole.setup_view import BoosterRoleSetupView

        register_setup(SetupEntry(
            key="boosterrole", label="Booster Role", emoji=Emojis.GEM,
            description="Let server boosters create and style one custom role.",
            factory=lambda author_id, guild_id: BoosterRoleSetupView(author_id, guild_id),
        ))
        # Startup pass: prune rows whose Discord role no longer resolves. Runs after
        # READY (cog_load itself is before the gateway is ready, so guilds aren't cached).
        self._startup_task = asyncio.create_task(self._startup_reconcile())

    def cog_unload(self) -> None:
        from src.core.setup_registry import unregister_setup

        self._reconcile_loop.cancel()
        if self._startup_task is not None:
            self._startup_task.cancel()
        unregister_setup("boosterrole")

    # ── reconcile / restore helpers ───────────────────────────────────────────

    async def _drop_dangling(self) -> set[int]:
        """Delete records whose role no longer resolves; return the healthy guild ids."""
        healthy: set[int] = set()
        for record in await service.list_all():
            guild = self.bot.get_guild(record.guild_id)
            if guild is None:
                continue  # can't verify while the guild isn't cached
            if guild.get_role(record.role_id) is None:
                await service.clear_by_role(record.guild_id, record.role_id)
            else:
                healthy.add(record.guild_id)
        return healthy

    async def _startup_reconcile(self) -> None:
        await self.bot.wait_until_ready()
        try:
            await self._drop_dangling()
        except Exception:
            log.exception("booster-role startup reconcile failed")

    @tasks.loop(seconds=config.RECONCILE_INTERVAL_SECONDS)
    async def _reconcile_loop(self) -> None:
        try:
            healthy = await self._drop_dangling()
            for guild_id in healthy:
                guild = self.bot.get_guild(guild_id)
                cfg = await service.get_config(guild_id)
                if guild is not None and cfg is not None and cfg.enabled:
                    await self._reposition(guild, cfg)
        except Exception:
            # tasks.loop only retries network errors; a transient DB error would otherwise
            # kill this loop permanently. Swallow and try again next tick.
            log.exception("booster-role reconcile loop failed")

    @_reconcile_loop.before_loop
    async def _before_reconcile(self) -> None:
        await self.bot.wait_until_ready()

    async def _reposition(self, guild: discord.Guild, cfg) -> None:
        """Cluster every booster role just above/below the anchor, in one bulk call."""
        if cfg is None or cfg.anchor_role_id is None:
            return
        anchor = guild.get_role(cfg.anchor_role_id)
        me = guild.me
        if anchor is None or me is None:
            return
        cohort = []
        for record in await service.list_roles(guild.id):
            role = guild.get_role(record.role_id)
            if role is not None and role < me.top_role:  # never try to move above the bot
                cohort.append(role)
        if not cohort:
            return
        base = anchor.position
        # Never target a slot at/above the bot's own role — Discord rejects the whole
        # bulk reposition if any target equals/exceeds me.top_role.position.
        ceiling = me.top_role.position - 1
        if cfg.hoist_above:
            positions = {role: min(base + i, ceiling) for i, role in enumerate(cohort, start=1)}
        else:
            positions = {role: max(1, base - i) for i, role in enumerate(cohort, start=1)}
        try:
            await guild.edit_role_positions(positions=positions, reason="booster role anchor")
        except discord.HTTPException:
            pass

    async def _restore_role(self, guild, member, record) -> discord.Role | None:
        """Resolve the member's booster role, recreating it from the stored state if
        the Discord role is gone, and ensure the member has it."""
        role = guild.get_role(record.role_id)
        if role is None:
            kwargs = {
                "name": record.name, "colour": discord.Colour(record.color),
                "reason": "restore booster role",
            }
            if record.icon and _has(guild, "ROLE_ICONS"):
                kwargs["display_icon"] = record.icon
            try:
                role = await guild.create_role(**kwargs)
            except discord.HTTPException:
                return None
            await service.update_role(guild.id, member.id, role_id=role.id)
        if role not in member.roles:
            try:
                await member.add_roles(role, reason="booster role")
            except discord.HTTPException:
                pass
        return role

    # ── listeners ─────────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member) -> None:
        started = before.premium_since is None and after.premium_since is not None
        stopped = before.premium_since is not None and after.premium_since is None
        if not (started or stopped):
            return
        cfg = await service.get_config(after.guild.id)
        if cfg is None or not cfg.enabled:
            return
        record = await service.get_booster_role(after.guild.id, after.id)
        if record is None:
            return  # nothing stored — on boost start they create one with ,br create
        if started:
            await self._restore_role(after.guild, after, record)
            await self._reposition(after.guild, cfg)
        else:  # stopped — drop the role from the member but keep the record for a reboost
            role = after.guild.get_role(record.role_id)
            if role is not None and role in after.roles:
                try:
                    await after.remove_roles(role, reason="boost ended")
                except discord.HTTPException:
                    pass

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role) -> None:
        # An admin deleted a custom role in Discord — clear its record, no dangling state.
        await service.clear_by_role(role.guild.id, role.id)

    # ── command helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _require_booster(ctx: commands.Context) -> None:
        if getattr(ctx.author, "premium_since", None) is None:
            raise BotError(
                "Only server boosters can do that. Boost the server to unlock a custom role!"
            )

    async def _own_role(self, ctx: commands.Context) -> discord.Role:
        record = await service.get_booster_role(ctx.guild.id, ctx.author.id)
        if record is None:
            raise BotError("You don't have a booster role yet. Use `,br create` first.")
        role = await self._restore_role(ctx.guild, ctx.author, record)
        if role is None:
            raise BotError("I couldn't access your booster role (do I have Manage Roles?).")
        return role

    # ── command tree ──────────────────────────────────────────────────────────

    @commands.group(name="boosterrole", aliases=["br", "brole"], invoke_without_command=True)
    @commands.guild_only()
    async def br(self, ctx: commands.Context) -> None:
        """Booster custom roles: boosters make and style one personal role."""
        await send_command_browser(ctx, ctx.command)

    # admin config (manage_guild) ----------------------------------------------

    @br.command(name="enable")
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def br_enable(self, ctx: commands.Context) -> None:
        """Turn booster roles on."""
        await service.set_enabled(ctx.guild.id, True)
        await ctx.send(embed=embeds.success(
            "Booster roles enabled. Boosters can now `,br create`."
        ))

    @br.command(name="disable")
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def br_disable(self, ctx: commands.Context) -> None:
        """Turn booster roles off."""
        await service.set_enabled(ctx.guild.id, False)
        await ctx.send(embed=embeds.success("Booster roles disabled."))

    @br.group(name="hoist", invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def br_hoist(self, ctx: commands.Context) -> None:
        """Whether custom roles sit above or below the anchor role."""
        await send_command_browser(ctx, ctx.command)

    @br_hoist.command(name="above")
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def br_hoist_above(self, ctx: commands.Context) -> None:
        """Place booster roles above the anchor."""
        await service.set_hoist_above(ctx.guild.id, True)
        await self._reposition(ctx.guild, await service.get_config(ctx.guild.id))
        await ctx.send(embed=embeds.success("Booster roles will sit **above** the anchor."))

    @br_hoist.command(name="below")
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def br_hoist_below(self, ctx: commands.Context) -> None:
        """Place booster roles below the anchor."""
        await service.set_hoist_above(ctx.guild.id, False)
        await self._reposition(ctx.guild, await service.get_config(ctx.guild.id))
        await ctx.send(embed=embeds.success("Booster roles will sit **below** the anchor."))

    @br.command(name="anchor")
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def br_anchor(self, ctx: commands.Context, *, role: discord.Role) -> None:
        """Set the role the booster-role cohort is positioned relative to."""
        await service.set_anchor(ctx.guild.id, role.id)
        cfg = await service.get_config(ctx.guild.id)
        await self._reposition(ctx.guild, cfg)
        where = "above" if cfg.hoist_above else "below"
        await ctx.send(embed=embeds.success(
            f"Anchor set to {role.mention}; booster roles cluster {where} it."
        ))

    @br.command(name="reset")
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def br_reset(self, ctx: commands.Context) -> None:
        """Reset booster-role config to defaults (disabled, no anchor)."""
        await service.reset_config(ctx.guild.id)
        await ctx.send(embed=embeds.success("Booster-role config reset to defaults."))

    @br.command(name="status")
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def br_status(self, ctx: commands.Context) -> None:
        """Show config plus which boost-gated perks the guild currently has."""
        cfg = await service.get_config(ctx.guild.id)
        anchor = ctx.guild.get_role(cfg.anchor_role_id) if (cfg and cfg.anchor_role_id) else None
        count = len(await service.list_roles(ctx.guild.id))
        perks = []
        if _has(ctx.guild, "ROLE_ICONS"):
            perks.append("role icons")
        if _has(ctx.guild, "ENHANCED_ROLE_COLORS") and _ENHANCED:
            perks.append("gradient/holo colors")
        e = embeds.info("", f"{Emojis.GEM} Booster Roles")
        e.add_field(name="Status", value="On" if (cfg and cfg.enabled) else "Off")
        hoist = "Above anchor" if (cfg is None or cfg.hoist_above) else "Below anchor"
        e.add_field(name="Hoist", value=hoist)
        e.add_field(name="Anchor", value=anchor.mention if anchor else "Not set")
        e.add_field(name="Booster roles", value=str(count))
        e.add_field(
            name="Boost perks",
            value=", ".join(perks) or "none yet (more boosts unlock icons & gradients)",
            inline=False,
        )
        await ctx.send(embed=e)

    # booster self-service (booster-only) --------------------------------------

    @br.command(name="create")
    @commands.guild_only()
    async def br_create(
        self, ctx: commands.Context, name: str, color: str, emoji: str | None = None
    ) -> None:
        """Create your booster role: name, hex color, optional emoji (quote spaced names)."""
        self._require_booster(ctx)
        cfg = await service.get_config(ctx.guild.id)
        if cfg is None or not cfg.enabled:
            raise BotError("Booster roles aren't enabled on this server.")
        if await service.get_booster_role(ctx.guild.id, ctx.author.id) is not None:
            raise BotError("You already have a booster role. Use `,br edit` to change it.")
        value = service.parse_color(color)
        # Discord caps a guild at 250 roles (external limit).
        if len(ctx.guild.roles) >= _ROLE_CAP:
            raise BotError("This server is at Discord's 250-role limit; an admin must free a slot.")
        kwargs = {
            "name": name[:100], "colour": discord.Colour(value),
            "reason": f"booster role for {ctx.author}",
        }
        skipped_icon = bool(emoji) and not _has(ctx.guild, "ROLE_ICONS")
        if emoji and not skipped_icon:
            kwargs["display_icon"] = emoji
        try:
            role = await ctx.guild.create_role(**kwargs)
        except discord.Forbidden:
            raise BotError("I need the Manage Roles permission to do that.") from None
        except discord.HTTPException:
            raise BotError("Discord rejected that role. Check the name and emoji.") from None
        try:
            await ctx.author.add_roles(role, reason="booster role")
        except discord.HTTPException:
            pass
        await service.create_role(
            ctx.guild.id, ctx.author.id, role.id, name[:100], value,
            emoji if (emoji and not skipped_icon) else None,
        )
        await self._reposition(ctx.guild, cfg)
        await ctx.send(embed=embeds.success(f"Created your booster role {role.mention}!"))
        if skipped_icon:
            await ctx.send(embed=embeds.info(
                "This server lacks role icons (needs more boosts), so I skipped the emoji."
            ))

    @br.group(name="edit", invoke_without_command=True)
    @commands.guild_only()
    async def br_edit(self, ctx: commands.Context) -> None:
        """Change your booster role's name, color, or emoji."""
        self._require_booster(ctx)
        await send_command_browser(ctx, ctx.command)

    @br_edit.command(name="name")
    @commands.guild_only()
    async def br_edit_name(self, ctx: commands.Context, *, name: str) -> None:
        """Rename your booster role."""
        self._require_booster(ctx)
        role = await self._own_role(ctx)
        try:
            await role.edit(name=name[:100], reason="booster role edit")
        except discord.HTTPException:
            raise BotError("I couldn't rename the role.") from None
        await service.update_role(ctx.guild.id, ctx.author.id, name=name[:100])
        await ctx.send(embed=embeds.success("Renamed your booster role."))

    @br_edit.command(name="color", aliases=["colour"])
    @commands.guild_only()
    async def br_edit_color(self, ctx: commands.Context, color: str) -> None:
        """Recolor your booster role (hex)."""
        self._require_booster(ctx)
        role = await self._own_role(ctx)
        value = service.parse_color(color)
        try:
            await role.edit(colour=discord.Colour(value), reason="booster role edit")
        except discord.HTTPException:
            raise BotError("I couldn't recolor the role.") from None
        await service.update_role(ctx.guild.id, ctx.author.id, color=value)
        await ctx.send(embed=embeds.success("Recolored your booster role."))

    @br_edit.command(name="emoji", aliases=["icon"])
    @commands.guild_only()
    async def br_edit_emoji(self, ctx: commands.Context, emoji: str) -> None:
        """Set your booster role's icon (needs the server's role-icon perk)."""
        self._require_booster(ctx)
        role = await self._own_role(ctx)
        if not _has(ctx.guild, "ROLE_ICONS"):
            await ctx.send(embed=embeds.info(
                "This server doesn't have role icons yet (needs more boosts)."
            ))
            return
        try:
            await role.edit(display_icon=emoji, reason="booster role edit")
        except discord.HTTPException:
            raise BotError("Discord didn't accept that emoji as a role icon.") from None
        await service.update_role(ctx.guild.id, ctx.author.id, icon=emoji)
        await ctx.send(embed=embeds.success("Updated your booster role icon."))

    @br.command(name="gradient")
    @commands.guild_only()
    async def br_gradient(self, ctx: commands.Context, color1: str, color2: str) -> None:
        """Give your booster role a two-color gradient (needs Enhanced Role Colors)."""
        self._require_booster(ctx)
        role = await self._own_role(ctx)
        c1, c2 = service.parse_color(color1), service.parse_color(color2)
        if not (_has(ctx.guild, "ENHANCED_ROLE_COLORS") and _ENHANCED):
            try:
                await role.edit(colour=discord.Colour(c1), reason="booster role (flat fallback)")
            except discord.HTTPException:
                raise BotError("I couldn't recolor the role.") from None
            await service.update_role(ctx.guild.id, ctx.author.id, color=c1)
            await ctx.send(embed=embeds.info(
                "Gradients need the Enhanced Role Colors perk, so I applied a flat color instead."
            ))
            return
        try:
            await role.edit(
                colour=discord.Colour(c1), secondary_colour=discord.Colour(c2),
                reason="booster role gradient",
            )
        except discord.HTTPException:
            raise BotError("Discord didn't accept that gradient.") from None
        await service.update_role(ctx.guild.id, ctx.author.id, color=c1)
        await ctx.send(embed=embeds.success("Applied a gradient to your booster role."))

    @br.command(name="holo", aliases=["holographic"])
    @commands.guild_only()
    async def br_holo(self, ctx: commands.Context) -> None:
        """Make your booster role holographic (needs Enhanced Role Colors)."""
        self._require_booster(ctx)
        role = await self._own_role(ctx)
        if not (_has(ctx.guild, "ENHANCED_ROLE_COLORS") and _ENHANCED):
            await ctx.send(embed=embeds.info(
                "Holographic roles need the Enhanced Role Colors perk (more boosts)."
            ))
            return
        primary, secondary, tertiary = _HOLO
        try:
            await role.edit(
                colour=discord.Colour(primary), secondary_colour=discord.Colour(secondary),
                tertiary_colour=discord.Colour(tertiary), reason="booster role holographic",
            )
        except discord.HTTPException:
            raise BotError("Discord didn't accept the holographic style.") from None
        await service.update_role(ctx.guild.id, ctx.author.id, color=primary)
        await ctx.send(embed=embeds.success("Made your booster role holographic. ✨"))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Boosterrole(bot))
