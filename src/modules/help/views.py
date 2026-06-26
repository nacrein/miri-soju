"""Interactive help components: category dropdown and command paginator."""

from __future__ import annotations

import discord
from discord.ext import commands

from src.core import embeds
from src.core.emojis import Emojis
from src.core.help_format import PREFIX, usage_embed

_TIMEOUT = 120  # views disable themselves after 2 minutes of inactivity


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


class CommandPaginator(_OwnerView):
    """Page through a cluster of related commands with ◀ ▶."""

    def __init__(self, author_id: int, group: list[commands.Command]) -> None:
        super().__init__(author_id)
        self._group = group
        self._index = 0
        self._sync_buttons()

    def current_embed(self) -> discord.Embed:
        e = usage_embed(self._group[self._index])
        e.set_footer(text=f"{self._index + 1} / {len(self._group)}")
        return e

    def _sync_buttons(self) -> None:
        self._prev.disabled = self._index == 0
        self._next.disabled = self._index == len(self._group) - 1

    @discord.ui.button(emoji=Emojis.ARROW_LEFT, style=discord.ButtonStyle.secondary)
    async def _prev(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        self._index = max(0, self._index - 1)
        self._sync_buttons()
        await interaction.response.edit_message(embed=self.current_embed(), view=self)

    @discord.ui.button(emoji=Emojis.ARROW_RIGHT, style=discord.ButtonStyle.secondary)
    async def _next(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        self._index = min(len(self._group) - 1, self._index + 1)
        self._sync_buttons()
        await interaction.response.edit_message(embed=self.current_embed(), view=self)


class _CategorySelect(discord.ui.Select):
    def __init__(self, categories: dict[str, list[commands.Command]]) -> None:
        self._categories = categories
        options = [
            discord.SelectOption(label=name, description=f"{len(cmds)} command(s)")
            for name, cmds in categories.items()
        ]
        super().__init__(placeholder="Pick a category…", options=options)

    async def callback(self, interaction: discord.Interaction) -> None:
        name = self.values[0]
        cmds = self._categories[name]
        lines = [
            f"{Emojis.BULLET} `{PREFIX}{c.qualified_name}` — {next(iter((c.help or '').splitlines()), 'No description.')}"
            for c in cmds
        ]
        e = embeds.info("\n".join(lines), f"{name} Commands")
        e.set_footer(text=f"Use {PREFIX}help <command> for details")
        await interaction.response.edit_message(embed=e, view=self.view)


class HelpMenu(_OwnerView):
    """Top-level help: a dropdown of categories."""

    def __init__(self, author_id: int, categories: dict[str, list[commands.Command]]) -> None:
        super().__init__(author_id)
        self.add_item(_CategorySelect(categories))
