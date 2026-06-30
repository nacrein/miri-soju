"""Reusable button paginators, locked to the invoker.

Two pagers live here so any feature can use them without importing another module:
``Paginator`` flips through a list of pre-built embeds (``paginate_lines`` builds
them), and ``CommandBrowser`` pages a command's family as help cards (◀ ▶ to page,
🔍 to jump by name, ✖ to close) — what a group shows when invoked bare.
"""

from __future__ import annotations

import discord
from discord.ext import commands

from src.core import embeds
from src.core.emojis import Emojis
from src.core.help_format import PREFIX, command_card, command_family

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
        self.message: discord.Message | None = None
        if len(pages) > 1:
            for i, page in enumerate(pages):
                page.set_footer(text=f"Page {i + 1}/{len(pages)}")
        self._sync_buttons()

    @property
    def _current(self) -> discord.Embed:
        return self._pages[self._index]

    async def start(self, ctx: commands.Context) -> None:
        """Send the first page; attach the buttons only if there's more than one."""
        # Later pages are shown via button edits, not ctx.send, so stamp the
        # invoker on every page now rather than relying on the send-time hook.
        for page in self._pages:
            embeds.apply_author(page, ctx.author)
        view = self if len(self._pages) > 1 else None
        self.message = await ctx.send(embed=self._current, view=view)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self._author_id:
            await interaction.response.send_message("This isn't your menu.", ephemeral=True)
            return False
        return True

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        if self.message is not None:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass

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


class _CommandSearchModal(discord.ui.Modal, title="Find a command"):
    """Type a command name to jump straight to its card in the browser."""

    name = discord.ui.TextInput(
        label="Command name", placeholder="e.g. reward add", required=True, max_length=100
    )

    def __init__(self, browser: CommandBrowser) -> None:
        super().__init__()
        self._browser = browser

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await self._browser.jump_to(interaction, str(self.name.value))


class CommandBrowser(discord.ui.View):
    """Page a command's family (the command then each subcommand) as help cards,
    locked to the invoker. ◀ ▶ page, 🔍 jumps to a command by name, ✖ closes.

    This is what a group shows when invoked without a subcommand (``,levels``) and
    what ``,help <group>`` shows. A lone command needs no browser — see
    ``send_command_browser``.
    """

    def __init__(
        self,
        author_id: int,
        family: list[commands.Command],
        category: str | None,
        prefix: str = PREFIX,
        *,
        invoker: discord.abc.User | None = None,
        url: str = "",
    ) -> None:
        super().__init__(timeout=_TIMEOUT)
        self._author_id = author_id
        self._family = family
        self._category = category
        self._prefix = prefix
        self._invoker = invoker
        self._url = url
        self._index = 0
        self.message: discord.Message | None = None
        self._sync()

    def card(self) -> discord.Embed:
        cmd = self._family[self._index]
        return command_card(
            cmd, self._prefix, author=self._invoker, category=self._category,
            page=self._index + 1, total=len(self._family), url=self._url or None,
        )

    def _sync(self) -> None:
        self._prev.disabled = self._index <= 0
        self._next.disabled = self._index >= len(self._family) - 1

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self._author_id:
            await interaction.response.send_message("This isn't your menu.", ephemeral=True)
            return False
        return True

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        if self.message is not None:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass

    def match_index(self, query: str) -> int | None:
        """The family index for ``query``: an exact name match wins, else the first
        whose qualified name contains it; ``None`` if nothing matches."""
        q = query.strip().lower()
        if not q:
            return None
        exact = next(
            (i for i, c in enumerate(self._family)
             if q in (c.qualified_name.lower(), c.name.lower())),
            None,
        )
        if exact is not None:
            return exact
        return next(
            (i for i, c in enumerate(self._family) if q in c.qualified_name.lower()),
            None,
        )

    async def jump_to(self, interaction: discord.Interaction, query: str) -> None:
        """Move to the command matching ``query``, or tell the user nothing did."""
        match = self.match_index(query)
        if match is None:
            await interaction.response.send_message(
                f"No command matching `{query}`.", ephemeral=True
            )
            return
        self._index = match
        self._sync()
        await interaction.response.edit_message(embed=self.card(), view=self)

    @discord.ui.button(emoji=Emojis.ARROW_LEFT, style=discord.ButtonStyle.secondary)
    async def _prev(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        self._index = max(0, self._index - 1)
        self._sync()
        await interaction.response.edit_message(embed=self.card(), view=self)

    @discord.ui.button(emoji=Emojis.ARROW_RIGHT, style=discord.ButtonStyle.secondary)
    async def _next(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        self._index = min(len(self._family) - 1, self._index + 1)
        self._sync()
        await interaction.response.edit_message(embed=self.card(), view=self)

    @discord.ui.button(emoji=Emojis.SEARCH, style=discord.ButtonStyle.secondary)
    async def _search(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await interaction.response.send_modal(_CommandSearchModal(self))

    @discord.ui.button(emoji=Emojis.CLOSE, style=discord.ButtonStyle.secondary)
    async def _close(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await interaction.response.defer()
        try:
            await interaction.message.delete()
        except discord.HTTPException:
            pass
        self.stop()


async def send_command_browser(
    ctx: commands.Context, command: commands.Command, *, category: str | None = None
) -> None:
    """Send ``command``'s family as browsable cards. A command with no subcommands
    is a single static card; a group opens the ◀ ▶ 🔍 ✖ browser. ``category``
    labels the footer (defaults to the command's cog name)."""
    family = command_family(command)
    category = category or (command.cog.qualified_name if command.cog else None)
    if len(family) == 1:
        await ctx.send(embed=command_card(
            command, ctx.clean_prefix, author=ctx.author, category=category,
        ))
        return
    view = CommandBrowser(
        ctx.author.id, family, category, ctx.clean_prefix, invoker=ctx.author,
    )
    view.message = await ctx.send(embed=view.card(), view=view)
