"""The ``,setup`` command: interactive control panels for non-command-savvy admins.

``,setup`` opens a picker of every module that registered a panel; ``,setup <module>``
opens that module's panel directly. The command reads only the core registry — each
feature registers its own panel in its ``cog_load`` — so this cog imports no feature
module. Gated to ``manage_guild``; once posted, each panel is locked to its invoker.
"""

from __future__ import annotations

from discord.ext import commands

from src.core import embeds, setup_registry
from src.modules.setup.views import SetupMenu


class Setup(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.hybrid_command(name="setup", extras={"example": "setup levels"})
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def setup_cmd(self, ctx: commands.Context, *, module: str | None = None) -> None:
        """Open an interactive control panel to configure a module."""
        entries = setup_registry.all_entries()
        if not entries:
            await ctx.send(embed=embeds.info("No setup panels are available yet."))
            return
        if module:
            entry = setup_registry.match_entry(module)
            if entry is None:
                keys = ", ".join(f"`{e.key}`" for e in entries)
                await ctx.send(embed=embeds.error(
                    f"No setup panel for `{module}`. Try: {keys}", "Unknown module"
                ))
                return
            wizard = entry.factory(ctx.author.id, ctx.guild.id)
            wizard.invoker = ctx.author
            await wizard.load()
            await wizard.start(ctx, wizard.render())
            return
        view = SetupMenu(ctx.author.id, ctx.guild.id, entries, invoker=ctx.author)
        await view.start(ctx, view.menu_embed())


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Setup(bot))
