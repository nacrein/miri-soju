"""The interactive embed builder: a live-preview message you shape with buttons,
modals, and a field dropdown, then **Send** to post the finished embed.

Design notes (the load-bearing ones):

* **One source of truth.** The builder's state IS the script dict that
  ``script.build`` consumes and ``script.to_script`` emits, so the preview, the
  Import/Export hatches, and the posted embed can never disagree.
* **The preview never errors.** ``render`` swallows ``build``'s ValueError and
  shows a friendly guide card instead; **Send** is disabled until the draft is
  postable, and re-checked on click.
* **No accidental branding.** The first send and every refresh bypass
  ``BotContext.send`` (via ``ctx.channel.send`` / ``edit_message``), so the
  invoker's avatar is never stamped onto a user-authored embed.
* Locked to the invoker, like every other view; controls disable on timeout or
  after Send/Cancel. Every mutation is a small sync ``apply_*`` method so the
  logic is unit-testable without a live Discord.
"""

from __future__ import annotations

import io
import json

import discord

from src.core import embeds
from src.core.emojis import Emojis
from src.modules.embed import script

_TIMEOUT = 300  # builders run longer than the 120s house default — you're typing.
_HINT = "**Embed builder**: shape it with the controls below, then press **Send**."


# ── modals (free-text entry; one per section) ─────────────────────────────────

class _ContentModal(discord.ui.Modal, title="Embed content"):
    def __init__(self, view: EmbedBuilderView) -> None:
        super().__init__()
        self._view = view
        d = view.data
        self.title_in = discord.ui.TextInput(
            label="Title", required=False, max_length=script.TITLE_MAX, default=d.get("title")
        )
        self.description_in = discord.ui.TextInput(
            label="Description", required=False, style=discord.TextStyle.paragraph,
            max_length=script.DESCRIPTION_MAX, default=d.get("description"),
        )
        self.url_in = discord.ui.TextInput(
            label="Title URL", required=False, max_length=script.URL_MAX,
            placeholder="https://…", default=d.get("url"),
        )
        self.color_in = discord.ui.TextInput(
            label="Color (hex)", required=False, max_length=20,
            placeholder="#5865f2", default=d.get("color"),
        )
        for item in (self.title_in, self.description_in, self.url_in, self.color_in):
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            self._view.apply_content(
                str(self.title_in.value), str(self.description_in.value),
                str(self.url_in.value), str(self.color_in.value),
            )
        except ValueError as exc:
            await interaction.response.send_message(embed=embeds.error(str(exc)), ephemeral=True)
            return
        await self._view.refresh(interaction)


class _AuthorFooterModal(discord.ui.Modal, title="Author & footer"):
    def __init__(self, view: EmbedBuilderView) -> None:
        super().__init__()
        self._view = view
        d = view.data
        self.author_in = discord.ui.TextInput(
            label="Author", required=False, max_length=script.AUTHOR_MAX, default=d.get("author")
        )
        self.footer_in = discord.ui.TextInput(
            label="Footer", required=False, max_length=script.FOOTER_MAX, default=d.get("footer")
        )
        for item in (self.author_in, self.footer_in):
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        self._view.apply_author_footer(str(self.author_in.value), str(self.footer_in.value))
        await self._view.refresh(interaction)


class _ImagesModal(discord.ui.Modal, title="Images"):
    def __init__(self, view: EmbedBuilderView) -> None:
        super().__init__()
        self._view = view
        d = view.data
        self.image_in = discord.ui.TextInput(
            label="Image URL", required=False, max_length=script.URL_MAX,
            placeholder="https://…", default=d.get("image"),
        )
        self.thumb_in = discord.ui.TextInput(
            label="Thumbnail URL", required=False, max_length=script.URL_MAX,
            placeholder="https://…", default=d.get("thumbnail"),
        )
        for item in (self.image_in, self.thumb_in):
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        self._view.apply_images(str(self.image_in.value), str(self.thumb_in.value))
        await self._view.refresh(interaction)


class _AddFieldModal(discord.ui.Modal, title="Add field"):
    def __init__(self, view: EmbedBuilderView) -> None:
        super().__init__()
        self._view = view
        self.name_in = discord.ui.TextInput(label="Name", max_length=script.FIELD_NAME_MAX)
        self.value_in = discord.ui.TextInput(
            label="Value", style=discord.TextStyle.paragraph, max_length=script.FIELD_VALUE_MAX
        )
        self.inline_in = discord.ui.TextInput(
            label="Inline? (yes/no)", required=False, max_length=5, placeholder="no"
        )
        for item in (self.name_in, self.value_in, self.inline_in):
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            self._view.apply_add_field(
                str(self.name_in.value), str(self.value_in.value), str(self.inline_in.value)
            )
        except ValueError as exc:
            await interaction.response.send_message(embed=embeds.error(str(exc)), ephemeral=True)
            return
        await self._view.refresh(interaction)


class _EditFieldModal(discord.ui.Modal, title="Edit field"):
    def __init__(self, view: EmbedBuilderView, index: int, field: dict) -> None:
        super().__init__()
        self._view = view
        self._index = index
        self.name_in = discord.ui.TextInput(
            label="Name", max_length=script.FIELD_NAME_MAX, default=field.get("name")
        )
        self.value_in = discord.ui.TextInput(
            label="Value", style=discord.TextStyle.paragraph,
            max_length=script.FIELD_VALUE_MAX, default=field.get("value"),
        )
        self.inline_in = discord.ui.TextInput(
            label="Inline? (yes/no)", required=False, max_length=5,
            default="yes" if field.get("inline") else "no",
        )
        self.delete_in = discord.ui.TextInput(
            label="Delete this field? (type yes)", required=False, max_length=5, placeholder="no"
        )
        for item in (self.name_in, self.value_in, self.inline_in, self.delete_in):
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        self._view.apply_edit_field(
            self._index, str(self.name_in.value), str(self.value_in.value),
            str(self.inline_in.value), str(self.delete_in.value),
        )
        await self._view.refresh(interaction)


class _ImportModal(discord.ui.Modal, title="Import JSON"):
    def __init__(self, view: EmbedBuilderView) -> None:
        super().__init__()
        self._view = view
        self.json_in = discord.ui.TextInput(
            label="Embed JSON", style=discord.TextStyle.paragraph,
            max_length=4000, placeholder=script.EXAMPLE,
        )
        self.add_item(self.json_in)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            self._view.apply_import(str(self.json_in.value))
        except ValueError as exc:
            msg = "That isn't valid JSON." if isinstance(exc, json.JSONDecodeError) else str(exc)
            await interaction.response.send_message(embed=embeds.error(msg), ephemeral=True)
            return
        await self._view.refresh(interaction)


# ── the field dropdown (point-and-click edit/remove) ──────────────────────────

class _FieldSelect(discord.ui.Select):
    """Lists the draft's fields; picking one opens a pre-filled edit modal. A
    Select needs ≥1 option, so the empty state is a single disabled placeholder."""

    def __init__(self) -> None:
        super().__init__(
            placeholder="Edit a field…", row=1,
            options=[discord.SelectOption(label="No fields yet", value="none")],
        )
        self.disabled = True

    def set_fields(self, fields: list[dict]) -> None:
        if fields:
            self.options = [
                discord.SelectOption(label=f"{i + 1}. {(f.get('name') or 'field')[:90]}", value=str(i))
                for i, f in enumerate(fields[:script.MAX_FIELDS])
            ]
            self.disabled = False
        else:
            self.options = [discord.SelectOption(label="No fields yet", value="none")]
            self.disabled = True

    async def callback(self, interaction: discord.Interaction) -> None:
        # The dropdown can be a frame behind the draft (a field was removed in a
        # concurrent modal). Re-sync rather than index into a stale position.
        index = int(self.values[0])
        field = self.view._field_at(index)
        if field is None:
            self.view._sync()
            await interaction.response.edit_message(embed=self.view.render(), view=self.view)
            return
        await interaction.response.send_modal(_EditFieldModal(self.view, index, field))


# ── the builder view ──────────────────────────────────────────────────────────

class EmbedBuilderView(discord.ui.View):
    def __init__(self, author_id: int, data: dict | None = None) -> None:
        super().__init__(timeout=_TIMEOUT)
        self._author_id = author_id
        self.data: dict = data or {}
        self.message: discord.Message | None = None
        self._field_select = _FieldSelect()
        self.add_item(self._field_select)
        self._sync()

    # ── lifecycle ─────────────────────────────────────────────────────────────

    async def start(self, ctx) -> None:
        """Post the initial builder. Uses ``ctx.channel.send`` (not ``ctx.send``)
        so ``BotContext`` doesn't stamp the invoker onto the user's preview."""
        self.message = await ctx.channel.send(content=_HINT, embed=self.render(), view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self._author_id:
            await interaction.response.send_message("This isn't your menu.", ephemeral=True)
            return False
        return True

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass

    async def refresh(self, interaction: discord.Interaction) -> None:
        """Re-sync controls and redraw the preview in place (no re-stamping)."""
        self._sync()
        await interaction.response.edit_message(content=_HINT, embed=self.render(), view=self)

    # ── rendering / validation ────────────────────────────────────────────────

    def render(self) -> discord.Embed:
        try:
            return script.build(self.data)
        except ValueError:
            return embeds.info(
                "This embed is empty. Use **Content** to add a title or description, "
                "or **Add field**, then press **Send** to post it.",
                f"{Emojis.SETTINGS} Embed builder",
            )

    def is_valid(self) -> bool:
        try:
            script.build(self.data)
            return True
        except ValueError:
            return False

    def _sync(self) -> None:
        self._send_btn.disabled = not self.is_valid()
        self._add_btn.disabled = len(self.data.get("fields", [])) >= script.MAX_FIELDS
        self._field_select.set_fields(self.data.get("fields", []))

    # ── state mutations (sync + testable; modals call these) ──────────────────

    def _field_at(self, index: int) -> dict | None:
        """The field at ``index``, or None if the dropdown selection is stale."""
        fields = self.data.get("fields", [])
        return fields[index] if 0 <= index < len(fields) else None

    def _set(self, key: str, value: str) -> None:
        cleaned = (value or "").strip()
        if cleaned:
            self.data[key] = cleaned
        else:
            self.data.pop(key, None)

    def apply_content(self, title: str, description: str, url: str, color: str) -> None:
        self._set("title", title)
        self._set("description", description)
        self._set("url", url)
        if (color or "").strip():
            script.parse_color(color.strip())  # validate; raises ValueError on bad hex
            self.data["color"] = color.strip()
        else:
            self.data.pop("color", None)

    def apply_author_footer(self, author: str, footer: str) -> None:
        self._set("author", author)
        self._set("footer", footer)

    def apply_images(self, image: str, thumbnail: str) -> None:
        self._set("image", image)
        self._set("thumbnail", thumbnail)

    def apply_add_field(self, name: str, value: str, inline: str) -> None:
        fields = self.data.setdefault("fields", [])
        if len(fields) >= script.MAX_FIELDS:
            raise ValueError(f"This embed already has the maximum {script.MAX_FIELDS} fields.")
        fields.append({"name": name.strip(), "value": value.strip(), "inline": script.parse_bool(inline)})

    def apply_edit_field(self, index: int, name: str, value: str, inline: str, delete: str) -> None:
        fields = self.data.get("fields", [])
        if not 0 <= index < len(fields):
            return
        if script.parse_bool(delete):
            fields.pop(index)
            if not fields:
                self.data.pop("fields", None)
            return
        fields[index] = {"name": name.strip(), "value": value.strip(), "inline": script.parse_bool(inline)}

    def apply_import(self, text: str) -> None:
        text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        data = json.loads(text)       # raises JSONDecodeError (a ValueError subclass)
        # Round-trip through build/to_script so stored state is normalized and
        # clamped: every value then fits its edit modal's max_length, the field
        # count is bounded, and unknown keys are dropped.
        self.data = script.to_script(script.build(data))

    # ── buttons ───────────────────────────────────────────────────────────────

    @discord.ui.button(label="Content", emoji=Emojis.MESSAGE_EDIT, style=discord.ButtonStyle.secondary, row=0)
    async def _content_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await interaction.response.send_modal(_ContentModal(self))

    @discord.ui.button(label="Author & footer", style=discord.ButtonStyle.secondary, row=0)
    async def _authorfooter_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await interaction.response.send_modal(_AuthorFooterModal(self))

    @discord.ui.button(label="Images", style=discord.ButtonStyle.secondary, row=0)
    async def _images_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await interaction.response.send_modal(_ImagesModal(self))

    @discord.ui.button(label="Add field", style=discord.ButtonStyle.secondary, row=2)
    async def _add_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await interaction.response.send_modal(_AddFieldModal(self))

    @discord.ui.button(label="Import JSON", style=discord.ButtonStyle.secondary, row=2)
    async def _import_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await interaction.response.send_modal(_ImportModal(self))

    @discord.ui.button(label="Export JSON", style=discord.ButtonStyle.secondary, row=2)
    async def _export_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if not self.data:
            await interaction.response.send_message(embed=embeds.info("Nothing to export yet."), ephemeral=True)
            return
        payload = json.dumps(self.data, indent=2, ensure_ascii=False)
        if len(payload) <= 1900:
            await interaction.response.send_message(f"```json\n{payload}\n```", ephemeral=True)
        else:  # too big for a code block — hand back a re-importable file, not clipped JSON
            file = discord.File(io.BytesIO(payload.encode("utf-8")), filename="embed.json")
            await interaction.response.send_message(file=file, ephemeral=True)

    @discord.ui.button(label="Send", emoji=Emojis.SUCCESS, style=discord.ButtonStyle.success, row=3)
    async def _send_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        try:
            built = script.build(self.data)  # belt-and-suspenders: the button is also gated
        except ValueError as exc:
            await interaction.response.send_message(embed=embeds.error(str(exc)), ephemeral=True)
            return
        # Acknowledge first (the 3s window), then post, so a slow/rate-limited
        # channel.send can't make the follow-up edit fail with Unknown Interaction.
        await interaction.response.defer()
        try:
            await interaction.channel.send(embed=built)  # raw send: no invoker author stamp
        except discord.HTTPException:
            await interaction.followup.send(
                embed=embeds.error("I couldn't post the embed here."), ephemeral=True
            )
            return
        for child in self.children:
            child.disabled = True
        await interaction.edit_original_response(
            content=None, embed=embeds.success("Embed posted."), view=self
        )
        self.stop()

    @discord.ui.button(label="Cancel", emoji=Emojis.CLOSE, style=discord.ButtonStyle.danger, row=3)
    async def _cancel_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await interaction.response.defer()
        try:
            await interaction.message.delete()
        except discord.HTTPException:
            pass
        self.stop()
