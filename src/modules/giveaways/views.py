"""The persistent Enter button shared by every giveaway message.

A DynamicItem (like buttonrole) so entries keep working across restarts without
re-registering each message's view; the giveaway is found by the message id."""

from __future__ import annotations

import discord

from src.core.emojis import Emojis
from src.modules.giveaways import service

_REPLIES = {
    "entered": "You're entered — good luck!",
    "left": "You've left this giveaway.",
    "ended": "This giveaway has already ended.",
    "missing": "This giveaway is no longer active.",
}


class GiveawayEnterButton(
    discord.ui.DynamicItem[discord.ui.Button], template=r"giveaway:enter"
):
    def __init__(self) -> None:
        super().__init__(discord.ui.Button(
            label="Enter", emoji=Emojis.TADA,
            style=discord.ButtonStyle.primary, custom_id="giveaway:enter",
        ))

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls()

    async def callback(self, interaction: discord.Interaction) -> None:
        result = await service.toggle_entry(interaction.message.id, interaction.user.id)
        await interaction.response.send_message(_REPLIES[result], ephemeral=True)


def giveaway_view() -> discord.ui.View:
    view = discord.ui.View(timeout=None)
    view.add_item(GiveawayEnterButton())
    return view
