"""Help system: ,help category dropdown and per-command usage embeds."""

from __future__ import annotations

from discord.ext import commands

from src.core import embeds
from src.core.emojis import Emojis
from src.core.help_format import usage_embed
from src.modules.help.views import HelpMenu


class Help(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    def _categories(self) -> dict[str, list[commands.Command]]:
        """Group visible commands by their cog (the category)."""
        cats: dict[str, list[commands.Command]] = {}
        for cog_name, cog in self.bot.cogs.items():
            visible = [c for c in cog.get_commands() if not c.hidden]
            if visible:
                cats[cog_name] = sorted(visible, key=lambda c: c.qualified_name)
        # loose commands with no cog
        loose = [c for c in self.bot.commands if c.cog is None and not c.hidden]
        if loose:
            cats["Other"] = sorted(loose, key=lambda c: c.qualified_name)
        return cats

    def _cluster_for(self, command: commands.Command) -> list[commands.Command]:
        """The commands in the same cog as this one (its cluster)."""
        if command.cog is None:
            return [command]
        return sorted(
            (c for c in command.cog.get_commands() if not c.hidden),
            key=lambda c: c.qualified_name,
        )

    @commands.command(name="help")
    async def help(self, ctx: commands.Context, *, command: str | None = None) -> None:
        """Show the command menu, or detailed help for one command."""
        if command is None:
            cats = self._categories()
            e = embeds.info(
                f"Pick a category below, or use `{ctx.clean_prefix}help <command>`.",
                f"{Emojis.QUESTION} Help",
            )
            await ctx.send(embed=e, view=HelpMenu(ctx.author.id, cats, ctx.clean_prefix))
            return

        cmd = self.bot.get_command(command)
        if cmd is None or cmd.hidden:
            await ctx.send(embed=embeds.error(f"No command called `{command}`."))
            return
        await ctx.send(embed=usage_embed(cmd, ctx.clean_prefix))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Help(bot))
