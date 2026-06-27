"""Button roles: add, remove, removeall, reset, list, with persistent buttons."""

from __future__ import annotations

import discord
from discord.ext import commands

from src.core import embeds
from src.modules.buttonrole import service

_STYLES = {
    "primary": discord.ButtonStyle.primary,
    "secondary": discord.ButtonStyle.secondary,
    "success": discord.ButtonStyle.success,
    "danger": discord.ButtonStyle.danger,
}


class ButtonRoleButton(discord.ui.DynamicItem[discord.ui.Button], template=r"buttonrole:(?P<role_id>\d+)"):
    def __init__(self, role_id: int, label=None, emoji=None, style=discord.ButtonStyle.secondary):
        self.role_id = role_id
        super().__init__(discord.ui.Button(
            label=label, emoji=emoji, style=style, custom_id=f"buttonrole:{role_id}"
        ))

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(int(match["role_id"]))

    async def callback(self, interaction: discord.Interaction) -> None:
        role = interaction.guild.get_role(self.role_id)
        if role is None:
            await interaction.response.send_message("That role no longer exists.", ephemeral=True)
            return
        member = interaction.user
        try:
            if role in member.roles:
                await member.remove_roles(role, reason="button role")
                await interaction.response.send_message(f"Removed {role.mention}.", ephemeral=True)
            else:
                await member.add_roles(role, reason="button role")
                await interaction.response.send_message(f"Added {role.mention}.", ephemeral=True)
        except discord.HTTPException:
            await interaction.response.send_message("I couldn't change that role.", ephemeral=True)


def _build_view(rows) -> discord.ui.View:
    view = discord.ui.View(timeout=None)
    for r in rows:
        view.add_item(ButtonRoleButton(
            r.role_id, label=r.label, emoji=r.emoji, style=_STYLES.get(r.style, discord.ButtonStyle.secondary)
        ))
    return view


class ButtonRoleCog(commands.Cog, name="ButtonRole"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        self.bot.add_dynamic_items(ButtonRoleButton)

    @commands.group(name="buttonrole", aliases=["br"], invoke_without_command=True)
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    @commands.guild_only()
    async def buttonrole(self, ctx) -> None:
        """Roles granted by buttons on a bot message."""
        await ctx.send(embed=embeds.info(
            "`,buttonrole add <message_link> <role> [style] [emoji] [label]` · "
            "`remove <message_link> <index>` · `removeall <message_link>` · `list` · `reset`"
        ))

    @buttonrole.command(name="add")
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def br_add(self, ctx, message: discord.Message, role: discord.Role,
                     style: str = "secondary", emoji: str | None = None, *, label: str | None = None) -> None:
        """Add a button to a bot message that toggles a role."""
        if message.author.id != self.bot.user.id:
            raise commands.BadArgument("I can only add buttons to my own messages.")
        if role >= ctx.guild.me.top_role:
            raise commands.BadArgument("That role is above my highest role.")
        if style not in _STYLES:
            raise commands.BadArgument(f"Style must be one of: {', '.join(_STYLES)}.")
        rows = await service.for_message(message.id)
        if len(rows) >= 25:
            raise commands.BadArgument("That message already has the maximum number of buttons.")
        await service.add(ctx.guild.id, message.id, role.id, label, emoji, style)
        await message.edit(view=_build_view(await service.for_message(message.id)))
        await ctx.send(embed=embeds.success(f"Added a button for {role.mention}."))

    @buttonrole.command(name="remove")
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def br_remove(self, ctx, message: discord.Message, index: int) -> None:
        """Remove one button by its index (see `,buttonrole list`)."""
        removed = await service.remove_one(message.id, index)
        if removed is None:
            raise commands.BadArgument("No button at that index.")
        rows = await service.for_message(message.id)
        await message.edit(view=_build_view(rows) if rows else None)
        await ctx.send(embed=embeds.success("Removed that button."))

    @buttonrole.command(name="removeall")
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def br_removeall(self, ctx, message: discord.Message) -> None:
        """Remove all buttons from a message."""
        count = await service.remove_message(message.id)
        try:
            await message.edit(view=None)
        except discord.HTTPException:
            pass
        await ctx.send(embed=embeds.success(f"Removed {count} button(s)."))

    @buttonrole.command(name="list")
    @commands.has_permissions(manage_roles=True)
    async def br_list(self, ctx) -> None:
        """List button roles in this server."""
        rows = await service.all_for(ctx.guild.id)
        if not rows:
            await ctx.send(embed=embeds.info("No button roles set."))
            return
        lines = [f"`#{i}` <@&{r.role_id}> · {r.label or r.emoji or 'button'}" for i, r in enumerate(rows, 1)]
        await ctx.send(embed=embeds.info("\n".join(lines)[:4000], f"Button Roles ({len(rows)})"))

    @buttonrole.command(name="reset")
    @commands.has_permissions(manage_roles=True)
    async def br_reset(self, ctx) -> None:
        """Remove all button roles in this server (records only)."""
        count = await service.clear(ctx.guild.id)
        await ctx.send(embed=embeds.success(f"Cleared {count} button role(s). Old messages keep their buttons until edited."))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ButtonRoleCog(bot))
