"""Fool-proof, ctx-free enforcement: the exemption gate, action wrappers, and logging.

Everything here acts on ``(guild, member, …)`` without a command context and swallows
``discord.HTTPException`` — automod must never raise into the message handler. The
exemption gate is the safety net: it returns True (do not act) for anyone protected.
"""

from __future__ import annotations

import logging
from datetime import timedelta

import discord

from src.core import checks, embeds
from src.core.emojis import Emojis
from src.modules.moderation import service as mod_service
from src.modules.serverlog.service import log_event

log = logging.getLogger(__name__)

_MAX_TIMEOUT_MIN = 28 * 24 * 60  # Discord's hard timeout cap


async def is_exempt(
    bot, guild, member, cfg, exempt_roles: set[int], exempt_channels: set[int], channel_id: int
) -> bool:
    """True == this member/channel must NOT be actioned. Cheap checks first."""
    if member is None or member.bot:
        return True
    if bot.user is not None and member.id == bot.user.id:
        return True
    if member.id == guild.owner_id:
        return True
    if channel_id in exempt_channels:
        return True
    if any(r.id in exempt_roles for r in member.roles):
        return True
    me = guild.me
    if me is None or member.top_role >= me.top_role:   # bot can't act above itself
        return True
    if cfg.exempt_mods:
        perms = member.guild_permissions
        if perms.manage_messages or perms.manage_guild or perms.administrator:
            return True
    if member.id in checks._staff_ids() or await bot.is_owner(member):
        return True
    return await mod_service.is_immune(guild.id, member.id, [r.id for r in member.roles])


# ── action wrappers (perm + hierarchy guarded, never raise) ────────────────────

async def try_delete(message) -> bool:
    try:
        await message.delete()
        return True
    except discord.HTTPException:
        return False


async def try_timeout(member, minutes: int, reason: str) -> bool:
    me = member.guild.me
    if me is None or not me.guild_permissions.moderate_members or member.top_role >= me.top_role:
        return False
    mins = max(1, min(minutes, _MAX_TIMEOUT_MIN))
    try:
        await member.timeout(timedelta(minutes=mins), reason=reason)
        return True
    except discord.HTTPException:
        return False


async def try_kick(member, reason: str) -> bool:
    me = member.guild.me
    if me is None or not me.guild_permissions.kick_members or member.top_role >= me.top_role:
        return False
    try:
        await member.kick(reason=reason)
        return True
    except discord.HTTPException:
        return False


async def try_ban(guild, member, reason: str) -> bool:
    me = guild.me
    if me is None or not me.guild_permissions.ban_members or member.top_role >= me.top_role:
        return False
    try:
        await guild.ban(member, reason=reason, delete_message_days=0)
        return True
    except discord.HTTPException:
        return False


async def perform(action: str, minutes: int | None, guild, member, reason: str) -> bool:
    """Run an escalated action. 'warn' is a no-op here (the delete + case already happened)."""
    if action == "timeout":
        return await try_timeout(member, minutes or 10, reason)
    if action == "kick":
        return await try_kick(member, reason)
    if action == "ban":
        return await try_ban(guild, member, reason)
    return True


# ── messaging ──────────────────────────────────────────────────────────────────

_LABEL = {"warn": "Warn", "kick": "Kick", "ban": "Ban"}


def action_text(action: str, minutes: int | None) -> str:
    return f"Timeout {minutes}m" if action == "timeout" else _LABEL.get(action, action.title())


def automod_embed(member, violation, action, minutes, strikes, *, dry_run: bool) -> discord.Embed:
    label = action_text(action, minutes)
    headline = f"[DRY-RUN] would {label.lower()}" if dry_run else label
    e = embeds.audit_log(
        f"AutoMod · {headline}", target=member, reason=violation.reason, icon=Emojis.SHIELD
    )
    e.add_field(name="Filter", value=violation.category)
    e.add_field(name="Strike", value=str(strikes))
    return e


async def log_action(bot, guild, member, violation, action, minutes, strikes, *, dry_run: bool) -> None:
    embed = automod_embed(member, violation, action, minutes, strikes, dry_run=dry_run)
    await log_event(bot, guild.id, embed, "mod")


async def dm_member(member, guild, violation, action, minutes) -> None:
    try:
        await member.send(embed=discord.Embed(
            title=f"{Emojis.SHIELD} AutoMod",
            description=(
                f"Your message in **{guild.name}** was removed ({violation.reason}). "
                f"Action taken: **{action_text(action, minutes).lower()}**."
            ),
            color=embeds.COLOR_ERROR,
        ))
    except discord.HTTPException:
        pass
