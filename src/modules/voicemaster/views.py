"""The persistent VoiceMaster control panel.

One ``VoicePanelView`` (timeout=None, static custom_ids) is registered with
``bot.add_view`` and serves *every* spawned channel: each button resolves the
clicker's owned channel from their live voice state and the DB at click time. So a
single panel message in the guild drives all temporary channels.
"""

from __future__ import annotations

import discord

from src.core import embeds
from src.core.emojis import Emojis
from src.modules.voicemaster import service, state


def panel_embed() -> discord.Embed:
    """The static panel embed posted in the panel channel."""
    return embeds.info(
        "Join the **create** voice channel to spawn your own room, then use the "
        "controls below (you must be in your channel):\n\n"
        f"{Emojis.MESSAGE_EDIT} **Rename** · 🔢 **Limit** the member count\n"
        f"{Emojis.LOCK} **Lock** / {Emojis.UNLOCK} **Unlock**: who can join\n"
        "👁️ **Hide** / **Reveal**: who can see it\n"
        f"{Emojis.CROWN} **Transfer** ownership · **Claim** an abandoned room",
        f"{Emojis.VOICE} VoiceMaster",
    )


# ── modals ──────────────────────────────────────────────────────────────────────

class _RenameModal(discord.ui.Modal, title="Rename channel"):
    def __init__(self, channel: discord.VoiceChannel) -> None:
        super().__init__()
        self.channel = channel
        self.name_in = discord.ui.TextInput(label="New name", max_length=100, default=channel.name)
        self.add_item(self.name_in)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        # Pre-reject the third rename in the window instead of hanging on Discord's
        # 2-per-10-min name bucket.
        if not state.rename_allowed(self.channel.id):
            await interaction.response.send_message(
                embed=embeds.warning("Only 2 renames per 10 minutes, try again soon."),
                ephemeral=True,
            )
            return
        new_name = str(self.name_in.value).strip()[:100] or self.channel.name
        try:
            await self.channel.edit(name=new_name, reason="VoiceMaster rename")
        except discord.HTTPException:
            await interaction.response.send_message(
                embed=embeds.error("I couldn't rename the channel."), ephemeral=True
            )
            return
        state.record_rename(self.channel.id)
        await interaction.response.send_message(
            embed=embeds.success("Channel renamed."), ephemeral=True
        )


class _LimitModal(discord.ui.Modal, title="User limit"):
    def __init__(self, channel: discord.VoiceChannel) -> None:
        super().__init__()
        self.channel = channel
        self.limit_in = discord.ui.TextInput(
            label="Limit (0-99, 0 = unlimited)", max_length=2, default=str(channel.user_limit)
        )
        self.add_item(self.limit_in)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            n = int(str(self.limit_in.value).strip())
        except ValueError:
            await interaction.response.send_message(
                embed=embeds.error("Give a whole number from 0 to 99."), ephemeral=True
            )
            return
        if not 0 <= n <= 99:
            await interaction.response.send_message(
                embed=embeds.error("Limit must be between 0 and 99."), ephemeral=True
            )
            return
        try:
            await self.channel.edit(user_limit=n, reason="VoiceMaster limit")
        except discord.HTTPException:
            await interaction.response.send_message(
                embed=embeds.error("I couldn't set the limit."), ephemeral=True
            )
            return
        await interaction.response.send_message(
            embed=embeds.success(f"User limit set to {n or 'unlimited'}."), ephemeral=True
        )


# ── transfer (member select) ────────────────────────────────────────────────────

class _TransferSelect(discord.ui.Select):
    def __init__(self, channel: discord.VoiceChannel) -> None:
        self.channel = channel
        members = [m for m in channel.members if not m.bot]
        options = [
            discord.SelectOption(label=m.display_name[:100], value=str(m.id)) for m in members
        ][:25]
        super().__init__(
            placeholder="Transfer ownership to…", min_values=1, max_values=1,
            options=options or [discord.SelectOption(label="No one else is here", value="none")],
        )
        if not options:
            self.disabled = True

    async def callback(self, interaction: discord.Interaction) -> None:
        target_id = int(self.values[0])
        live = interaction.guild.get_channel(self.channel.id)
        if live is None or not any(m.id == target_id for m in live.members):
            await interaction.response.send_message(
                embed=embeds.error("That member isn't in the channel anymore."), ephemeral=True
            )
            return
        await service.transfer_ownership(interaction.guild.id, self.channel.id, target_id)
        await interaction.response.edit_message(
            embed=embeds.success(f"Ownership transferred to <@{target_id}>."), view=None
        )


class _TransferView(discord.ui.View):
    def __init__(self, channel: discord.VoiceChannel) -> None:
        super().__init__(timeout=120)
        self.add_item(_TransferSelect(channel))


# ── the persistent panel ────────────────────────────────────────────────────────

class VoicePanelView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)

    async def _resolve(self, interaction: discord.Interaction):
        """The clicker's current voice channel + its record, or None (with a reply)."""
        voice = getattr(interaction.user, "voice", None)
        channel = voice.channel if voice else None
        if channel is None:
            await interaction.response.send_message(
                embed=embeds.error("Join your VoiceMaster channel first."), ephemeral=True
            )
            return None
        record = await service.get_channel_by_id(interaction.guild.id, channel.id)
        if record is None:
            await interaction.response.send_message(
                embed=embeds.error("This isn't a VoiceMaster channel."), ephemeral=True
            )
            return None
        return record, channel

    async def _require_owner(self, interaction: discord.Interaction):
        resolved = await self._resolve(interaction)
        if resolved is None:
            return None
        record, channel = resolved
        if interaction.user.id != record.owner_id:
            await interaction.response.send_message(
                embed=embeds.error("Only the channel owner can do that."), ephemeral=True
            )
            return None
        return record, channel

    async def _set_perm(self, interaction, channel, *, reason, **perms) -> None:
        try:
            await channel.set_permissions(interaction.guild.default_role, reason=reason, **perms)
        except discord.HTTPException:
            await interaction.response.send_message(
                embed=embeds.error("I couldn't update the channel."), ephemeral=True
            )
            return
        await interaction.response.send_message(embed=embeds.success(reason + "."), ephemeral=True)

    # ── row 0 ────────────────────────────────────────────────────────────────
    @discord.ui.button(
        label="Rename", emoji=Emojis.MESSAGE_EDIT,
        style=discord.ButtonStyle.secondary, custom_id="vm:rename", row=0,
    )
    async def _rename(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        owned = await self._require_owner(interaction)
        if owned is not None:
            await interaction.response.send_modal(_RenameModal(owned[1]))

    @discord.ui.button(
        label="Limit", emoji="🔢", style=discord.ButtonStyle.secondary, custom_id="vm:limit", row=0
    )
    async def _limit(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        owned = await self._require_owner(interaction)
        if owned is not None:
            await interaction.response.send_modal(_LimitModal(owned[1]))

    @discord.ui.button(
        label="Lock", emoji=Emojis.LOCK,
        style=discord.ButtonStyle.secondary, custom_id="vm:lock", row=0,
    )
    async def _lock(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        owned = await self._require_owner(interaction)
        if owned is not None:
            await self._set_perm(interaction, owned[1], reason="Channel locked", connect=False)

    @discord.ui.button(
        label="Unlock", emoji=Emojis.UNLOCK,
        style=discord.ButtonStyle.secondary, custom_id="vm:unlock", row=0,
    )
    async def _unlock(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        owned = await self._require_owner(interaction)
        if owned is not None:
            await self._set_perm(interaction, owned[1], reason="Channel unlocked", connect=None)

    # ── row 1 ────────────────────────────────────────────────────────────────
    @discord.ui.button(
        label="Hide", emoji="🙈", style=discord.ButtonStyle.secondary, custom_id="vm:hide", row=1
    )
    async def _hide(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        owned = await self._require_owner(interaction)
        if owned is not None:
            await self._set_perm(interaction, owned[1], reason="Channel hidden", view_channel=False)

    @discord.ui.button(
        label="Reveal", emoji="👁️", style=discord.ButtonStyle.secondary, custom_id="vm:reveal", row=1
    )
    async def _reveal(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        owned = await self._require_owner(interaction)
        if owned is not None:
            await self._set_perm(
                interaction, owned[1], reason="Channel revealed", view_channel=None
            )

    @discord.ui.button(
        label="Transfer", emoji=Emojis.CROWN,
        style=discord.ButtonStyle.secondary, custom_id="vm:transfer", row=1,
    )
    async def _transfer(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        owned = await self._require_owner(interaction)
        if owned is not None:
            await interaction.response.send_message(
                embed=embeds.info("Pick who to transfer ownership to:"),
                view=_TransferView(owned[1]), ephemeral=True,
            )

    @discord.ui.button(
        label="Claim", emoji=Emojis.CROWN,
        style=discord.ButtonStyle.primary, custom_id="vm:claim", row=1,
    )
    async def _claim(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        resolved = await self._resolve(interaction)
        if resolved is None:
            return
        record, channel = resolved
        if record.owner_id == interaction.user.id:
            await interaction.response.send_message(
                embed=embeds.info("You already own this channel."), ephemeral=True
            )
            return
        if any(m.id == record.owner_id for m in channel.members):
            await interaction.response.send_message(
                embed=embeds.error("The owner is still here, you can't claim it."), ephemeral=True
            )
            return
        await service.transfer_ownership(interaction.guild.id, channel.id, interaction.user.id)
        await interaction.response.send_message(
            embed=embeds.success("You're now the owner of this channel."), ephemeral=True
        )
