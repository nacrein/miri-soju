"""Autoroles: roles handed to every member automatically on join.

Distinct from reactionrole/buttonrole, which are opt-in via an interaction — these
are applied with no action from the member, the moment they join."""

from __future__ import annotations

import discord
from discord.ext import commands

from src.core import embeds
from src.core.paginator import send_command_browser
from src.modules.autoroles import service


def _assignable(guild: discord.Guild, role: discord.Role) -> bool:
    """A role the bot may actually grant: not @everyone, not integration-managed,
    and below the bot's top role in the hierarchy."""
    return not role.managed and not role.is_default() and role < guild.me.top_role


class AutoRoles(commands.Cog, name="AutoRoles"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.group(name="autorole", aliases=["autoroles"], invoke_without_command=True)
    @commands.has_permissions(manage_roles=True)
    @commands.guild_only()
    async def autorole(self, ctx) -> None:
        """Roles given to members automatically when they join."""
        await send_command_browser(ctx, ctx.command)

    @autorole.command(name="add")
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def autorole_add(self, ctx, *, role: discord.Role) -> None:
        """Add a role to auto-assign on join."""
        if role.is_default() or role.managed:
            raise commands.BadArgument("I can't auto-assign @everyone or a managed role.")
        if role >= ctx.guild.me.top_role:
            raise commands.BadArgument("That role is above my highest role.")
        if not await service.add(ctx.guild.id, role.id):
            raise commands.BadArgument(f"{role.mention} is already an autorole.")
        await ctx.send(embed=embeds.success(f"{role.mention} will be given to new members."))

    @autorole.command(name="remove", aliases=["del"])
    @commands.has_permissions(manage_roles=True)
    async def autorole_remove(self, ctx, *, role: discord.Role) -> None:
        """Stop auto-assigning a role."""
        if not await service.remove(ctx.guild.id, role.id):
            raise commands.BadArgument(f"{role.mention} isn't an autorole.")
        await ctx.send(embed=embeds.success(f"{role.mention} is no longer an autorole."))

    @autorole.command(name="list")
    @commands.has_permissions(manage_roles=True)
    async def autorole_list(self, ctx) -> None:
        """List this server's autoroles."""
        role_ids = await service.list_roles(ctx.guild.id)
        if not role_ids:
            await ctx.send(
                embed=embeds.info("No autoroles set. Add one with `,autorole add <role>`.")
            )
            return
        lines = [f"<@&{rid}>" for rid in role_ids]
        await ctx.send(embed=embeds.info("\n".join(lines), f"Autoroles ({len(role_ids)})"))

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        if member.bot:
            return
        role_ids = await service.list_roles(member.guild.id)
        if not role_ids:
            return
        roles = [
            role
            for rid in role_ids
            if (role := member.guild.get_role(rid)) is not None
            and _assignable(member.guild, role)
        ]
        if roles:
            try:
                await member.add_roles(*roles, reason="autorole")
            except discord.HTTPException:
                pass


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AutoRoles(bot))
