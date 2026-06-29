"""Shared base views for interactive, invoker-locked menus.

``OwnerView`` factors out the author-lock + timeout-disable + cached-message
pattern that every interactive view in the bot repeats. ``WizardView`` adds the
contract the ``,setup`` panels share: an async ``load`` (read current config into
the view) and a sync ``render`` (build the status embed), with a ready-made
``refresh`` that reloads and redraws in place after a control mutates config.

Only the newer views build on these; the older ones (the embed builder, the help
menu, the command browser) keep their own copies to avoid churn.
"""

from __future__ import annotations

import discord

from src.core import embeds

_TIMEOUT = 180  # panels disable themselves after 3 minutes of inactivity


class OwnerView(discord.ui.View):
    """A view only its invoker may use. Disables its controls on timeout.

    ``invoker`` (the full user, set by the launcher) is stamped onto rendered
    embeds for the house author-row style; ``message`` is the posted message, kept
    so ``on_timeout`` can grey the controls in place.
    """

    def __init__(
        self,
        author_id: int,
        *,
        invoker: discord.abc.User | None = None,
        timeout: float = _TIMEOUT,
    ) -> None:
        super().__init__(timeout=timeout)
        self._author_id = author_id
        self.invoker = invoker
        self.message: discord.Message | None = None

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

    def _stamp(self, embed: discord.Embed) -> discord.Embed:
        """Apply the invoker's author row, the same touch ``BotContext.send`` adds."""
        return embeds.apply_author(embed, self.invoker)

    async def start(self, ctx, embed: discord.Embed) -> discord.Message:
        """Post the view and remember the message (so timeouts can grey it)."""
        self.message = await ctx.send(embed=embed, view=self)
        return self.message


class WizardView(OwnerView):
    """A live config control panel: read config, render it, mutate, redraw.

    Subclasses implement ``load`` (async — read config into the view, then sync the
    controls) and ``render`` (sync — build the status embed from that state). A
    control handler persists its change via the module's existing service setter,
    then calls ``refresh`` to reload and redraw the panel in the same message.
    """

    async def load(self) -> None:
        raise NotImplementedError

    def render(self) -> discord.Embed:
        raise NotImplementedError

    async def refresh(self, interaction: discord.Interaction) -> None:
        await self.load()
        await interaction.response.edit_message(embed=self.render(), view=self)
