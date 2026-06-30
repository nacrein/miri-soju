"""createembed and embedcopy: build an embed with the interactive builder (or
straight from a JSON script), and the inverse — copy an embed back to JSON."""

from __future__ import annotations

import io
import json

import discord
from discord.ext import commands

from src.modules.embed import script
from src.modules.embed.views import EmbedBuilderView


class EmbedBuilder(commands.Cog, name="Embed"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.command(name="createembed", aliases=["embed", "ce"])
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def createembed(self, ctx, *, code: str | None = None) -> None:
        """Open the interactive embed builder, or post one straight from JSON.

        With no argument you get a live-preview builder (buttons, a field
        dropdown, and Import/Export JSON). Pass a JSON script to post immediately,
        the classic way."""
        if not code:
            await EmbedBuilderView(ctx.author.id).start(ctx)
            return
        code = code.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        try:
            built = script.build(json.loads(code))
        except json.JSONDecodeError:
            raise commands.BadArgument("That isn't valid JSON.") from None
        except ValueError as exc:
            raise commands.BadArgument(str(exc)) from exc
        try:
            await ctx.send(embed=built)
        except discord.HTTPException:
            raise commands.BadArgument(
                "Discord rejected that embed. Check your URLs and that no field is blank."
            ) from None

    @commands.command(name="embedcopy", aliases=["ec"])
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def embedcopy(self, ctx, message: discord.Message) -> None:
        """Copy a message's first embed as a JSON script (paste it into `,ce`)."""
        if not message.embeds:
            raise commands.BadArgument("That message has no embed.")
        payload = json.dumps(script.to_script(message.embeds[0]), indent=2, ensure_ascii=False)
        if len(payload) <= 1900:
            await ctx.send(f"```json\n{payload}\n```")
        else:  # large embed — send the full JSON as a file so it stays re-importable
            await ctx.send(file=discord.File(io.BytesIO(payload.encode("utf-8")), filename="embed.json"))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(EmbedBuilder(bot))
