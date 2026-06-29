"""The ``,setup`` module picker: a dropdown of the registered setup panels.

Picking a module builds its panel from the registry's factory and swaps it into the
same message (the help menu does the same with ``open_category``). The picker reads
only the registry, so it never imports a feature module.
"""

from __future__ import annotations

import discord

from src.core import embeds
from src.core.emojis import Emojis
from src.core.setup_registry import SetupEntry
from src.core.views import OwnerView


class _ModuleSelect(discord.ui.Select):
    def __init__(self, entries: list[SetupEntry]) -> None:
        super().__init__(
            placeholder="Pick a module to configure…",
            options=[
                discord.SelectOption(
                    label=e.label, value=e.key,
                    description=(e.description[:100] if e.description else None),
                    emoji=e.emoji,
                )
                for e in entries
            ],
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        await self.view.open_wizard(self.values[0], interaction)


class SetupMenu(OwnerView):
    """Landing menu for ``,setup`` with no argument: just the module dropdown."""

    def __init__(
        self,
        author_id: int,
        guild_id: int,
        entries: list[SetupEntry],
        *,
        invoker: discord.abc.User | None = None,
    ) -> None:
        super().__init__(author_id, invoker=invoker)
        self._guild_id = guild_id
        self._entries = {e.key: e for e in entries}
        self.add_item(_ModuleSelect(entries))

    def menu_embed(self) -> discord.Embed:
        e = embeds.info(
            "Pick a module from the menu below to open its setup panel.",
            f"{Emojis.SETTINGS} Server setup",
        )
        return self._stamp(e)

    async def open_wizard(self, key: str, interaction: discord.Interaction) -> None:
        entry = self._entries.get(key)
        if entry is None:  # registry changed under us (cog reload) — bail gracefully
            await interaction.response.send_message(
                embed=embeds.error("That module is no longer available."), ephemeral=True
            )
            return
        await interaction.response.defer()  # ack within 3s; load() does DB I/O
        try:
            wizard = entry.factory(self._author_id, self._guild_id)
            wizard.invoker = self.invoker
            wizard.message = self.message
            await wizard.load()
            await interaction.edit_original_response(embed=wizard.render(), view=wizard)
        except Exception:
            await interaction.followup.send(
                embed=embeds.error("I couldn't open that panel — try again in a moment."),
                ephemeral=True,
            )
            return
        self.stop()
