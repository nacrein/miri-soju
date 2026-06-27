"""Reusable button paginator: page a list of embeds with ◀ ▶, locked to the invoker.

Generalises the help module's CommandPaginator so any command with a long list
can page it. Build pages with ``paginate_lines`` (or pass your own embeds) and
``await Paginator(ctx.author.id, pages).start(ctx)``.
"""

from __future__ import annotations

import discord
from discord.ext import commands

from src.core import embeds
from src.core.emojis import Emojis

_TIMEOUT = 120  # views disable themselves after 2 minutes of inactivity


def paginate_lines(lines: list[str], title: str, per_page: int = 15) -> list[discord.Embed]:
    """Chunk text lines into a list of info embeds, one per page."""
    if not lines:
        return [embeds.info("Nothing to show.", title)]
    return [
        embeds.info("\n".join(lines[i : i + per_page]), title)
        for i in range(0, len(lines), per_page)
    ]


class Paginator(discord.ui.View):
    """Page through pre-built embeds. Only the invoker can use the buttons."""

    def __init__(self, author_id: int, pages: list[discord.Embed]) -> None:
        super().__init__(timeout=_TIMEOUT)
        self._author_id = author_id
        self._pages = pages
        self._index = 0
        if len(pages) > 1:
            for i, page in enumerate(pages):
                page.set_footer(text=f"Page {i + 1}/{len(pages)}")
        self._sync_buttons()

    @property
    def _current(self) -> discord.Embed:
        return self._pages[self._index]

    async def start(self, ctx: commands.Context) -> None:
        """Send the first page; attach the buttons only if there's more than one."""
        view = self if len(self._pages) > 1 else None
        await ctx.send(embed=self._current, view=view)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self._author_id:
            await interaction.response.send_message("This isn't your menu.", ephemeral=True)
            return False
        return True

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True

    def _sync_buttons(self) -> None:
        self._prev.disabled = self._index == 0
        self._next.disabled = self._index >= len(self._pages) - 1

    @discord.ui.button(emoji=Emojis.ARROW_LEFT, style=discord.ButtonStyle.secondary)
    async def _prev(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        self._index = max(0, self._index - 1)
        self._sync_buttons()
        await interaction.response.edit_message(embed=self._current, view=self)

    @discord.ui.button(emoji=Emojis.ARROW_RIGHT, style=discord.ButtonStyle.secondary)
    async def _next(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        self._index = min(len(self._pages) - 1, self._index + 1)
        self._sync_buttons()
        await interaction.response.edit_message(embed=self._current, view=self)
