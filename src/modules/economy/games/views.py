"""Interactive game views. State is server-side; the stake is already escrowed.

Each view: only the player who started it may act; buttons disable on finish or
timeout; abandoning forfeits the escrowed stake (only a real win pays out).
"""

from __future__ import annotations

import discord

from src.core import embeds
from src.core.emojis import Emojis
from src.modules.economy import config, service
from src.modules.economy.games import logic


def _fmt(n: int) -> str:
    return f"{n:,}"


class _GameView(discord.ui.View):
    game_name = "game"

    def __init__(self, player_id: int, stake: int = 0, session_id: str | None = None) -> None:
        super().__init__(timeout=90)
        self._player_id = player_id
        self._stake = stake
        self._session_id = session_id  # pairs this game's stake to its resolution
        self._resolved = False  # set True once the game pays out or settles
        self.message: discord.Message | None = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self._player_id:
            await interaction.response.send_message("This isn't your game.", ephemeral=True)
            return False
        return True

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        # Abandoned mid-game: the escrowed stake is forfeit. Log the resolution.
        if not self._resolved and self._stake > 0:
            await service.log_forfeit(self._player_id, self._stake, self.game_name, self._session_id)
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass


# ── ladder ──────────────────────────────────────────────────────────────────

class LadderView(_GameView):
    game_name = "ladder"
    def __init__(self, player_id: int, stake: int, session_id: str | None = None) -> None:
        super().__init__(player_id, stake, session_id=session_id)
        self._rung = -1  # -1 = before the first rung
        self._rungs = config.LADDER_RUNGS

    def _current_mult(self) -> float:
        return self._rungs[self._rung][0] if self._rung >= 0 else 0.0

    def embed(self, *, status: str | None = None) -> discord.Embed:
        mult = self._current_mult()
        banked = int(self._stake * mult)
        e = embeds.info("", f"{Emojis.LADDER} Ladder")
        e.add_field(name="Stake", value=f"{Emojis.BITS} {_fmt(self._stake)}")
        e.add_field(name="Rung", value=f"{self._rung + 1} / {len(self._rungs)}")
        e.add_field(name="Cash-out value", value=f"{Emojis.BITS} {_fmt(banked)} ({mult:.2f}x)")
        if self._rung + 1 < len(self._rungs):
            next_mult, bust = self._rungs[self._rung + 1]
            e.add_field(
                name="Next rung",
                value=f"{next_mult:.2f}x · {int(bust*100)}% bust risk",
                inline=False,
            )
        if status:
            e.description = status
        return e

    async def _finish(self, interaction: discord.Interaction, payout: int, text: str) -> None:
        new_wallet = await service.payout_winnings(self._player_id, payout, self._session_id)
        for child in self.children:
            child.disabled = True
        e = self.embed(status=f"{text}\nWallet: {_fmt(new_wallet)}")
        self._resolved = True
        await interaction.response.edit_message(embed=e, view=self)
        self.stop()

    @discord.ui.button(label="Climb", style=discord.ButtonStyle.success)
    async def climb(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        next_index = self._rung + 1
        if logic.ladder_climb_busts(next_index, self._rungs):
            await self._finish(interaction, 0, f"{Emojis.LOSE} You busted and lost your stake.")
            return
        self._rung = next_index
        if self._rung + 1 >= len(self._rungs):
            payout = int(self._stake * self._current_mult())
            await self._finish(interaction, payout, f"{Emojis.WIN} Top rung! Auto-cashed out.")
            return
        await interaction.response.edit_message(embed=self.embed(), view=self)

    @discord.ui.button(label="Cash out", style=discord.ButtonStyle.primary)
    async def cash_out(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if self._rung < 0:
            await self._finish(interaction, self._stake, "You cashed out before climbing (stake returned).")
            return
        payout = int(self._stake * self._current_mult())
        await self._finish(interaction, payout, f"{Emojis.WIN} Cashed out at {self._current_mult():.2f}x!")


# ── crash ───────────────────────────────────────────────────────────────────

class CrashView(_GameView):
    game_name = "crash"
    def __init__(self, player_id: int, stake: int, session_id: str | None = None) -> None:
        super().__init__(player_id, stake, session_id=session_id)
        self._mult = config.CRASH_START_MULT
        self._crashed = False

    def embed(self, *, status: str | None = None) -> discord.Embed:
        e = embeds.info("", f"{Emojis.CRASH} Crash")
        e.add_field(name="Stake", value=f"{Emojis.BITS} {_fmt(self._stake)}")
        e.add_field(name="Multiplier", value=f"**{self._mult:.2f}x**")
        e.add_field(name="Cash-out value", value=f"{Emojis.BITS} {_fmt(int(self._stake*self._mult))}")
        if status:
            e.description = status
        else:
            e.description = "Press **Tick** to climb, **Cash out** to bank it. It can crash anytime."
        return e

    @discord.ui.button(label="Tick", style=discord.ButtonStyle.success)
    async def tick(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if logic.crash_tick(config.CRASH_BASE_CRASH_CHANCE):
            self._crashed = True
            for child in self.children:
                child.disabled = True
            await service.payout_winnings(self._player_id, 0, self._session_id)
            self._resolved = True
            e = self.embed(status=f"{Emojis.LOSE} Crashed at {self._mult:.2f}x! Stake lost.")
            await interaction.response.edit_message(embed=e, view=self)
            self.stop()
            return
        self._mult += config.CRASH_TICK_GROWTH
        await interaction.response.edit_message(embed=self.embed(), view=self)

    @discord.ui.button(label="Cash out", style=discord.ButtonStyle.primary)
    async def cash_out(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        payout = int(self._stake * self._mult)
        new_wallet = await service.payout_winnings(self._player_id, payout, self._session_id)
        for child in self.children:
            child.disabled = True
        e = self.embed(status=f"{Emojis.WIN} Cashed out at {self._mult:.2f}x!\nWallet: {_fmt(new_wallet)}")
        self._resolved = True
        await interaction.response.edit_message(embed=e, view=self)
        self.stop()


# ── blackjack ───────────────────────────────────────────────────────────────

def _show(cards: list[tuple[str, str]]) -> str:
    return " ".join(f"{r}{s}" for r, s in cards)


class BlackjackView(_GameView):
    game_name = "blackjack"
    def __init__(self, player_id: int, stake: int, session_id: str | None = None) -> None:
        super().__init__(player_id, stake, session_id=session_id)
        self._game = logic.BlackjackGame()

    def embed(self, *, reveal_dealer: bool = False, status: str | None = None) -> discord.Embed:
        g = self._game
        dealer_show = _show(g.dealer) if reveal_dealer else f"{_show(g.dealer[:1])} ??"
        dealer_total = logic.hand_total(g.dealer) if reveal_dealer else "?"
        e = embeds.info("", f"{Emojis.CARD} Blackjack")
        e.add_field(name=f"Your hand ({logic.hand_total(g.player)})", value=_show(g.player), inline=False)
        e.add_field(name=f"Dealer ({dealer_total})", value=dealer_show, inline=False)
        e.add_field(name="Stake", value=f"{Emojis.BITS} {_fmt(self._stake)}", inline=False)
        if status:
            e.description = status
        return e

    async def _settle(self, interaction: discord.Interaction) -> None:
        g = self._game
        result = g.result()
        if result == "natural":
            payout = int(self._stake * config.BLACKJACK_NATURAL_PAYOUT)
            text = f"{Emojis.WIN} Blackjack! Paid 3:2."
        elif result == "win":
            payout = int(self._stake * config.BLACKJACK_PAYOUT)
            text = f"{Emojis.WIN} You win!"
        elif result == "push":
            payout = self._stake  # stake returned
            text = "Push · your stake is returned."
        else:  # lose or bust
            payout = 0
            text = f"{Emojis.LOSE} You {'busted' if result == 'bust' else 'lose'}."
        new_wallet = await service.payout_winnings(self._player_id, payout, self._session_id)
        for child in self.children:
            child.disabled = True
        e = self.embed(reveal_dealer=True, status=f"{text}\nWallet: {_fmt(new_wallet)}")
        self._resolved = True
        await interaction.response.edit_message(embed=e, view=self)
        self.stop()

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.success)
    async def hit(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        self._game.hit()
        if logic.hand_total(self._game.player) > 21:
            await self._settle(interaction)
            return
        await interaction.response.edit_message(embed=self.embed(), view=self)

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.primary)
    async def stand(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        self._game.dealer_play()
        await self._settle(interaction)


# ── hi-lo ────────────────────────────────────────────────────────────────────

class HiLoView(_GameView):
    game_name = "hilo"

    def __init__(self, player_id: int, stake: int, session_id: str | None = None) -> None:
        super().__init__(player_id, stake, session_id=session_id)
        self._card = logic.hilo_draw()
        self._mult = 1.0
        self._sync_labels()

    def _sync_labels(self) -> None:
        higher, lower = logic.hilo_multipliers(self._card, config.HOUSE_EDGE)
        self.higher.label = f"Higher or same ({higher:.2f}x)"
        self.lower.label = f"Lower or same ({lower:.2f}x)"

    def embed(self, *, status: str | None = None) -> discord.Embed:
        e = embeds.info("", f"{Emojis.CARD} Hi-Lo")
        e.add_field(name="Card", value=f"**{logic.hilo_face(self._card)}**")
        e.add_field(name="Stake", value=f"{Emojis.BITS} {_fmt(self._stake)}")
        e.add_field(
            name="Cash-out value",
            value=f"{Emojis.BITS} {_fmt(int(self._stake * self._mult))} ({self._mult:.2f}x)",
        )
        e.description = status or "Will the next card be higher or lower? Cash out anytime."
        return e

    async def _guess(self, interaction: discord.Interaction, higher: bool) -> None:
        higher_mult, lower_mult = logic.hilo_multipliers(self._card, config.HOUSE_EDGE)
        nxt = logic.hilo_draw()
        won = nxt >= self._card if higher else nxt <= self._card
        self._card = nxt
        if not won:
            for child in self.children:
                child.disabled = True
            wallet = await service.payout_winnings(self._player_id, 0, self._session_id)
            self._resolved = True
            e = self.embed(
                status=f"{Emojis.LOSE} It was **{logic.hilo_face(nxt)}**. Busted, stake lost.\n"
                       f"Wallet: {_fmt(wallet)}"
            )
            await interaction.response.edit_message(embed=e, view=self)
            self.stop()
            return
        self._mult *= higher_mult if higher else lower_mult
        self._sync_labels()
        face = logic.hilo_face(nxt)
        e = self.embed(status=f"{Emojis.WIN} **{face}** · you're at {self._mult:.2f}x.")
        await interaction.response.edit_message(embed=e, view=self)

    @discord.ui.button(label="Higher or same", style=discord.ButtonStyle.success)
    async def higher(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self._guess(interaction, True)

    @discord.ui.button(label="Lower or same", style=discord.ButtonStyle.success)
    async def lower(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self._guess(interaction, False)

    @discord.ui.button(label="Cash out", style=discord.ButtonStyle.primary)
    async def cash_out(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        payout = int(self._stake * self._mult)
        new_wallet = await service.payout_winnings(self._player_id, payout, self._session_id)
        for child in self.children:
            child.disabled = True
        self._resolved = True
        e = self.embed(
            status=f"{Emojis.WIN} Cashed out at {self._mult:.2f}x!\nWallet: {_fmt(new_wallet)}"
        )
        await interaction.response.edit_message(embed=e, view=self)
        self.stop()
