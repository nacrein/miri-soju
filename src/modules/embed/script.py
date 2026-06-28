"""The embed ⇄ JSON script: the single source of truth for the embed builder.

``build`` turns a script dict into a ``discord.Embed`` (validating, clamping, and
parsing color); ``to_script`` is the exact inverse. The interactive builder, the
``,ce <json>`` fast path, the Import modal, and ``,ec`` all funnel through these
two functions, so what you preview is always what gets posted — they can never
disagree on a length cap or a color rule.

These live apart from the cog and the views so both can import them without an
import cycle (the views never reach back into the cog).
"""

from __future__ import annotations

import discord

EXAMPLE = '{"title": "Hello", "description": "Body text", "color": "#5865f2"}'

# Field length caps, mirrored by every modal's max_length so the preview and the
# posted embed always agree. Note DESCRIPTION is 4000, not Discord's 4096.
TITLE_MAX = 256
DESCRIPTION_MAX = 4000
AUTHOR_MAX = 256
FOOTER_MAX = 2048
FIELD_NAME_MAX = 256
FIELD_VALUE_MAX = 1024
URL_MAX = 1024
MAX_FIELDS = 25

_TRUE_WORDS = {"yes", "y", "true", "1", "on"}


def parse_bool(text: str | None) -> bool:
    """Forgiving yes/no parse for the ``inline`` toggle modals must type as text."""
    return (text or "").strip().lower() in _TRUE_WORDS


def parse_color(text: str) -> discord.Color:
    """Parse a color like ``#5865f2``, ``0x5865f2``, ``rgb(…)``, or a plain
    decimal integer (as third-party embed JSON often stores it). Raises
    ``ValueError`` on anything else — the same rule ``build`` enforces."""
    s = str(text).strip()
    try:
        if s.isdigit():  # a bare decimal like 5793266
            value = int(s)
            if not 0 <= value <= 0xFFFFFF:
                raise ValueError
            return discord.Color(value)
        return discord.Color.from_str(s)
    except ValueError:
        raise ValueError("`color` must be a hex like `#5865f2`.")


def build(data: dict) -> discord.Embed:
    """Build an embed from a script dict. Raises ValueError on bad input."""
    if not isinstance(data, dict):
        raise ValueError("The script must be a JSON object.")
    e = discord.Embed()
    if data.get("title"):
        e.title = str(data["title"])[:TITLE_MAX]
    if data.get("description"):
        e.description = str(data["description"])[:DESCRIPTION_MAX]
    if data.get("url"):
        e.url = str(data["url"])
    if data.get("color"):
        e.color = parse_color(str(data["color"]))
    if data.get("author"):
        e.set_author(name=str(data["author"])[:AUTHOR_MAX])
    if data.get("footer"):
        e.set_footer(text=str(data["footer"])[:FOOTER_MAX])
    if data.get("image"):
        e.set_image(url=str(data["image"]))
    if data.get("thumbnail"):
        e.set_thumbnail(url=str(data["thumbnail"]))
    fields = data.get("fields") or []
    if not isinstance(fields, list):
        raise ValueError("`fields` must be a list.")
    if len(fields) > MAX_FIELDS:
        raise ValueError(f"A maximum of {MAX_FIELDS} fields is allowed (got {len(fields)}).")
    for field in fields:
        if not isinstance(field, dict):
            raise ValueError("Each field must be an object with `name` and `value`.")
        # Discord rejects a blank field name/value; fall back to a zero-width space
        # so a whitespace-only entry can't make a postable-looking embed fail on send.
        name = str(field.get("name", ""))
        value = str(field.get("value", ""))
        e.add_field(
            name=name[:FIELD_NAME_MAX] if name.strip() else "​",
            value=value[:FIELD_VALUE_MAX] if value.strip() else "​",
            inline=bool(field.get("inline", False)),
        )
    if not (e.title or e.description or e.fields):
        raise ValueError("The embed needs at least a title, description, or one field.")
    return e


def to_script(e: discord.Embed) -> dict:
    out: dict = {}
    if e.title:
        out["title"] = e.title
    if e.description:
        out["description"] = e.description
    if e.url:
        out["url"] = e.url
    if e.color:
        out["color"] = str(e.color)
    if e.author and e.author.name:
        out["author"] = e.author.name
    if e.footer and e.footer.text:
        out["footer"] = e.footer.text
    if e.image and e.image.url:
        out["image"] = e.image.url
    if e.thumbnail and e.thumbnail.url:
        out["thumbnail"] = e.thumbnail.url
    if e.fields:
        out["fields"] = [{"name": f.name, "value": f.value, "inline": f.inline} for f in e.fields]
    return out
