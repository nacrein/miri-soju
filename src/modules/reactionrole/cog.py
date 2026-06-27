"""Reaction roles: add, remove, list, clear, plus the raw-reaction listeners."""

from __future__ import annotations

import discord
from discord.ext import commands

from src.core import embeds
from src.modules.reactionrole import service


class ReactionRole(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.group(name="reactionrole", aliases=["rr"], invoke_without_command=True)
    @commands.has_permissions(manage_roles=True)
    @commands.guild_only()
    async def reactionrole(self, ctx) -> None:
        """Roles granted by reacting to a message."""
        await ctx.send(embed=embeds.info(
            "`,reactionrole add <message_link> <emoji> <role>` · `remove <message_link> <emoji>` · `list` · `clear`"
        ))

    @reactionrole.command(name="add")
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True, add_reactions=True)
    async def rr_add(self, ctx, message: discord.Message, emoji: str, *, role: discord.Role) -> None:
        """Bind an emoji on a message to a role."""
        if role >= ctx.guild.me.top_role:
            raise commands.BadArgument("That role is above my highest role.")
        try:
            await message.add_reaction(emoji)
        except discord.HTTPException:
            raise commands.BadArgument("I couldn't react with that emoji.")
        await service.add(ctx.guild.id, message.id, emoji, role.id)
        await ctx.send(embed=embeds.success(f"Reacting with {emoji} now grants {role.mention}."))

    @reactionrole.command(name="remove")
    @commands.has_permissions(manage_roles=True)
    async def rr_remove(self, ctx, message: discord.Message, emoji: str) -> None:
        """Unbind an emoji on a message."""
        if not await service.remove(message.id, emoji):
            raise commands.BadArgument("No reaction role for that emoji on that message.")
        await ctx.send(embed=embeds.success("Removed that reaction role."))

    @reactionrole.command(name="list")
    @commands.has_permissions(manage_roles=True)
    async def rr_list(self, ctx) -> None:
        """List reaction roles in this server."""
        rows = await service.all_for(ctx.guild.id)
        if not rows:
            await ctx.send(embed=embeds.info("No reaction roles set."))
            return
        lines = [f"{r.emoji} → <@&{r.role_id}> · [message](https://discord.com/channels/{r.guild_id}/_/{r.message_id})" for r in rows]
        await ctx.send(embed=embeds.info("\n".join(lines)[:4000], f"Reaction Roles ({len(rows)})"))

    @reactionrole.command(name="clear")
    @commands.has_permissions(manage_roles=True)
    async def rr_clear(self, ctx) -> None:
        """Remove all reaction roles in this server."""
        count = await service.clear(ctx.guild.id)
        await ctx.send(embed=embeds.success(f"Cleared {count} reaction role(s)."))

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        await self._apply(payload, add=True)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent) -> None:
        await self._apply(payload, add=False)

    async def _apply(self, payload: discord.RawReactionActionEvent, *, add: bool) -> None:
        if payload.guild_id is None or payload.user_id == self.bot.user.id:
            return
        role_id = await service.role_for(payload.message_id, str(payload.emoji))
        if role_id is None:
            return
        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return
        member = guild.get_member(payload.user_id)
        role = guild.get_role(role_id)
        if member is None or role is None or role >= guild.me.top_role:
            return
        try:
            if add:
                await member.add_roles(role, reason="reaction role")
            else:
                await member.remove_roles(role, reason="reaction role")
        except discord.HTTPException:
            pass


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ReactionRole(bot))
