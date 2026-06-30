"""The per-option vote buttons and the live tally embed.

Each button is a persistent DynamicItem whose custom id carries the poll's message
id and the option index, so votes keep working across restarts. Clicking records a
single vote (changing it moves it) and redraws the tally in place."""

from __future__ import annotations

import discord

from src.core import embeds
from src.core.emojis import Emojis
from src.modules.polls import service

_BAR_LEN = 10


def _bar(pct: float) -> str:
    filled = round(pct / 100 * _BAR_LEN)
    return "▰" * filled + "▱" * (_BAR_LEN - filled)


def poll_embed(poll, options: list[str], counts: dict[int, int]) -> discord.Embed:
    total = sum(counts.values())
    lines = []
    for idx, label in enumerate(options):
        count = counts.get(idx, 0)
        pct = (count / total * 100) if total else 0.0
        lines.append(f"**{label}** — {count} ({pct:.0f}%)\n{_bar(pct)}")
    footer = (f"Closed · {total} vote(s)" if poll.closed
              else f"{total} vote(s) · one per person")
    return embeds.info("\n".join(lines) + f"\n\n*{footer}*", f"{Emojis.POLL} {poll.question}")


class PollVoteButton(
    discord.ui.DynamicItem[discord.ui.Button],
    template=r"poll:(?P<message_id>\d+):(?P<idx>\d+)",
):
    def __init__(self, message_id: int, idx: int, *, label: str | None = None) -> None:
        self.message_id = message_id
        self.idx = idx
        super().__init__(discord.ui.Button(
            label=label or f"Option {idx + 1}",
            style=discord.ButtonStyle.secondary,
            custom_id=f"poll:{message_id}:{idx}",
        ))

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(int(match["message_id"]), int(match["idx"]))

    async def callback(self, interaction: discord.Interaction) -> None:
        result = await service.vote(interaction.message.id, interaction.user.id, self.idx)
        if result != "ok":
            note = "This poll is closed." if result == "closed" else "This poll is gone."
            await interaction.response.send_message(note, ephemeral=True)
            return
        data = await service.render_data(interaction.message.id)
        if data is None:
            await interaction.response.defer()
            return
        poll, options, counts = data
        await interaction.response.edit_message(embed=poll_embed(poll, options, counts))


def poll_view(message_id: int, options: list[str]) -> discord.ui.View:
    view = discord.ui.View(timeout=None)
    for idx, label in enumerate(options):
        view.add_item(PollVoteButton(message_id, idx, label=label[:80]))
    return view
