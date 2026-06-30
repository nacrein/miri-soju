"""The one-time economy rules agreement: a plain embed + an "I agree" button.

Shown by the Economy cog's ``cog_check`` the first time a user runs any economy command
(see cog.py). Accepting is recorded once (globally, per user) and the gate never shows
again. Edit ``_RULES`` to change the wording.
"""

from __future__ import annotations

import discord

from src.core import embeds
from src.core.emojis import Emojis
from src.core.views import OwnerView
from src.modules.economy import service

_RULES = (
    "Heads up before you use the economy.\n\n"
    "By continuing you agree that you will not:\n"
    f"{Emojis.BULLET} Exploit bugs or glitches. Report them to staff instead.\n"
    f"{Emojis.BULLET} Use alt accounts to farm or move currency between accounts.\n"
    f"{Emojis.BULLET} Automate or script commands (macros, self-bots).\n\n"
    "Staff can reset any balance gained by breaking these rules.\n\n"
    "Press **I agree** to confirm you have read this and will not abuse the bot."
)


def agreement_embed() -> discord.Embed:
    return embeds.info(_RULES, f"{Emojis.BITS} Economy rules")


class AgreementView(OwnerView):
    """Invoker-locked consent prompt with a single "I agree" button."""

    @discord.ui.button(label="I agree", emoji=Emojis.SUCCESS, style=discord.ButtonStyle.success)
    async def _agree(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await service.record_agreement(interaction.user.id)
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(
            embed=embeds.success("You're all set. Run your command again."), view=self
        )
        self.stop()
