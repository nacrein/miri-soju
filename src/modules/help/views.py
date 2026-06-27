"""Interactive help components: the category dropdown.

Picking a category swaps the message to that category's command listing — every
top-level command in one ansi codeblock, with groups marked by their subcommand
count (``vault (4)..``). There's no per-command paging: ``,help <command>`` shows
a single command's card.
"""

from __future__ import annotations

import discord
from discord.ext import commands

from src.core import embeds
from src.core.help_format import PREFIX, command_listing
from src.modules.help.categories import category_description, category_emoji

_TIMEOUT = 120  # views disable themselves after 2 minutes of inactivity
_MAX_OPTIONS = 25  # Discord's hard cap on options per select
_MAX_SELECTS = 5   # ...and on action rows (selects) per view → 125 categories


class _OwnerView(discord.ui.View):
    """Base view that only the original invoker may interact with."""

    def __init__(self, author_id: int) -> None:
        super().__init__(timeout=_TIMEOUT)
        self._author_id = author_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self._author_id:
            await interaction.response.send_message(
                "This isn't your menu.", ephemeral=True
            )
            return False
        return True

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True


class _CategorySelect(discord.ui.Select):
    def __init__(self, categories: dict[str, list[commands.Command]], prefix: str = PREFIX) -> None:
        self._prefix = prefix
        options = [
            discord.SelectOption(
                label=name,
                description=(category_description(name) or None),
                emoji=category_emoji(name),
            )
            for name in categories
        ]
        super().__init__(placeholder="Select a category…", options=options)

    async def callback(self, interaction: discord.Interaction) -> None:
        await self.view.open_category(self.values[0], interaction)


class HelpMenu(_OwnerView):
    """Top-level help: the category dropdown(s).

    Before a category is chosen the message shows the landing embed; choosing one
    edits the message to that category's full command listing. Categories are
    chunked across selects (25 each, up to 5) so the menu keeps working however
    many cogs get added.
    """

    def __init__(
        self,
        author_id: int,
        categories: dict[str, list[commands.Command]],
        prefix: str = PREFIX,
        *,
        invoker: discord.abc.User | None = None,
    ) -> None:
        super().__init__(author_id)
        self._categories = categories
        self._prefix = prefix
        self._invoker = invoker
        names = list(categories)
        for start in range(0, len(names), _MAX_OPTIONS):
            selects = sum(1 for c in self.children if isinstance(c, discord.ui.Select))
            if selects >= _MAX_SELECTS:
                break
            chunk = {n: categories[n] for n in names[start:start + _MAX_OPTIONS]}
            self.add_item(_CategorySelect(chunk, prefix))

    def category_embed(self, name: str) -> discord.Embed:
        """The listing shown when a category is picked: its blurb plus every
        top-level command in one ansi codeblock."""
        cmds = self._categories[name]
        body = f"## `{name}` commands\n"
        blurb = category_description(name)
        if blurb:
            body += f"> {blurb}\n"
        body += command_listing(cmds)

        e = discord.Embed(description=body, color=embeds.COLOR_DUSK)
        if self._invoker is not None:
            e.set_author(
                name=self._invoker.display_name,
                icon_url=self._invoker.display_avatar.url,
            )
        groups = sum(1 for c in cmds if isinstance(c, commands.Group))
        e.set_footer(text=f"{len(cmds)} commands • {groups} groups")
        return e

    async def open_category(self, name: str, interaction: discord.Interaction) -> None:
        await interaction.response.edit_message(embed=self.category_embed(name), view=self)
