"""createembed and embedcopy: build an embed from a JSON script, and the inverse."""

from __future__ import annotations

import json

import discord
from discord.ext import commands

from src.core import embeds

_EXAMPLE = '{"title": "Hello", "description": "Body text", "color": "#5865f2"}'


def _build(data: dict) -> discord.Embed:
    """Build an embed from a script dict. Raises ValueError on bad input."""
    if not isinstance(data, dict):
        raise ValueError("The script must be a JSON object.")
    e = discord.Embed()
    if "title" in data:
        e.title = str(data["title"])[:256]
    if "description" in data:
        e.description = str(data["description"])[:4000]
    if "url" in data:
        e.url = str(data["url"])
    if "color" in data:
        try:
            e.color = discord.Color.from_str(str(data["color"]))
        except ValueError:
            raise ValueError("`color` must be a hex like `#5865f2`.")
    if "author" in data:
        e.set_author(name=str(data["author"])[:256])
    if "footer" in data:
        e.set_footer(text=str(data["footer"])[:2048])
    if "image" in data:
        e.set_image(url=str(data["image"]))
    if "thumbnail" in data:
        e.set_thumbnail(url=str(data["thumbnail"]))
    for field in data.get("fields", [])[:25]:
        e.add_field(
            name=str(field.get("name", "\u200b"))[:256],
            value=str(field.get("value", "\u200b"))[:1024],
            inline=bool(field.get("inline", False)),
        )
    if not (e.title or e.description or e.fields):
        raise ValueError("The embed needs at least a title, description, or one field.")
    return e


def _to_script(e: discord.Embed) -> dict:
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


class EmbedBuilder(commands.Cog, name="Embed"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.command(name="createembed", aliases=["embed", "ce"])
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def createembed(self, ctx, *, code: str | None = None) -> None:
        """Post an embed from a JSON script."""
        if not code:
            await ctx.send(embed=embeds.info(f"Give a JSON script, e.g.\n```json\n{_EXAMPLE}\n```"))
            return
        code = code.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        try:
            data = json.loads(code)
            built = _build(data)
        except json.JSONDecodeError:
            raise commands.BadArgument("That isn't valid JSON.")
        except ValueError as exc:
            raise commands.BadArgument(str(exc))
        await ctx.send(embed=built)

    @commands.command(name="embedcopy", aliases=["ec"])
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def embedcopy(self, ctx, message: discord.Message) -> None:
        """Copy a message's first embed as a JSON script."""
        if not message.embeds:
            raise commands.BadArgument("That message has no embed.")
        script = json.dumps(_to_script(message.embeds[0]), indent=2, ensure_ascii=False)
        await ctx.send(f"```json\n{script[:1900]}\n```")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(EmbedBuilder(bot))
