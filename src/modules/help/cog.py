"""Help system: the ,help category menu and per-command "Command: X" cards."""

from __future__ import annotations

import discord
from discord.ext import commands

from src.core import embeds
from src.core.paginator import send_command_browser
from src.modules.help.categories import CATEGORIES, DEFAULT_CATEGORY, cog_to_category
from src.modules.help.views import HelpMenu

# Links shown on the help menu and as the card title's hyperlink. Leave blank to
# omit them entirely (no broken links). Fill in once you have a site/server.
WEBSITE_URL = ""
SUPPORT_URL = ""

def _menu_blurb(prefix: str) -> str:
    """The landing blurb: how to navigate, plus the syntax key. Written in our own
    words (a syntax key, not a copy of anyone else's help text)."""
    return (
        f"Choose a category to browse, or run `{prefix}help <command>` for the "
        "full breakdown.\n"
        "-# Reading syntax · `<x>` is required · `[x]` is optional · `x…` repeats"
    )


def _links_value() -> str:
    """The 'website / support server' line, built from whatever links are set."""
    parts = []
    if WEBSITE_URL:
        parts.append(f"view the commands [**on the website**]({WEBSITE_URL})")
    if SUPPORT_URL:
        parts.append(f"join our [**support server**]({SUPPORT_URL})")
    if not parts:
        return ""
    return ">>> Need a hand? " + ", or ".join(parts) + "."


class Help(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    def _categories(self) -> dict[str, list[commands.Command]]:
        """Group visible top-level commands into the broad categories from
        ``categories.py``, in that file's order, dropping any that end up empty.

        Still fully automatic: commands and cogs are read from the live registry,
        and a cog not named in the map falls into ``DEFAULT_CATEGORY``; so a new
        module shows up the instant it loads, just unsorted until you place it."""
        cog_for = cog_to_category()
        buckets: dict[str, list[commands.Command]] = {name: [] for name in CATEGORIES}

        for cog_name, cog in self.bot.cogs.items():
            category = cog_for.get(cog_name, DEFAULT_CATEGORY)
            buckets[category].extend(c for c in cog.get_commands() if not c.hidden)
        # loose commands with no cog land in the default bucket too
        for c in self.bot.commands:
            if c.cog is None and not c.hidden:
                buckets[DEFAULT_CATEGORY].append(c)

        return {
            name: sorted(cmds, key=lambda c: c.qualified_name)
            for name, cmds in buckets.items()
            if cmds
        }

    def _category_of(self, command: commands.Command) -> str:
        """The display category a command belongs to (via its cog)."""
        cog_name = command.cog.qualified_name if command.cog else None
        return cog_to_category().get(cog_name, DEFAULT_CATEGORY)

    def _menu_embed(self, ctx: commands.Context) -> discord.Embed:
        e = discord.Embed(description=_menu_blurb(ctx.clean_prefix), color=embeds.COLOR_DUSK)
        e.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
        if self.bot.user:
            e.set_thumbnail(url=self.bot.user.display_avatar.url)
        links = _links_value()
        if links:
            e.add_field(name="​", value=links, inline=False)
        return e

    @commands.hybrid_command(name="help", aliases=["h"])
    async def help(self, ctx: commands.Context, *, command: str | None = None) -> None:
        """Show the command menu, or detailed help for one command."""
        if command is None:
            view = HelpMenu(
                ctx.author.id,
                self._categories(),
                ctx.clean_prefix,
                invoker=ctx.author,
            )
            await ctx.send(embed=self._menu_embed(ctx), view=view)
            return

        cmd = self.bot.get_command(command)
        if cmd is None or cmd.hidden:
            await ctx.send(embed=embeds.error(f"No command called `{command}`."))
            return

        # A plain command shows a single card; a group opens the ◀ ▶ 🔍 ✖ browser
        # over the group and each of its subcommands.
        await send_command_browser(ctx, cmd, category=self._category_of(cmd))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Help(bot))
