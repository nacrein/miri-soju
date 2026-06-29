"""Server prefix configuration. Default is ','; only the server owner may change it."""

from __future__ import annotations

from discord.ext import commands

from src.core import embeds
from src.core.emojis import Emojis
from src.modules.prefix import service

_MAX_PREFIX_LEN = 5


class Prefix(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        from src.core.setup_registry import SetupEntry, register_setup
        from src.modules.prefix.setup_view import PrefixSetupView

        register_setup(SetupEntry(
            key="prefix", label="Prefix", emoji=Emojis.SETTINGS,
            description="Change the command prefix (server owner only).",
            factory=lambda author_id, guild_id: PrefixSetupView(author_id, guild_id),
        ))

    def cog_unload(self) -> None:
        from src.core.setup_registry import unregister_setup

        unregister_setup("prefix")

    @commands.command(name="prefix", extras={"example": "prefix !"})
    @commands.guild_only()
    async def prefix(self, ctx: commands.Context, *, new: str | None = None) -> None:
        """Show this server's prefix, or set a new one (server owner only)."""
        if new is None:
            current = await service.get_prefix(ctx.guild.id)
            await ctx.send(embed=embeds.info(
                f"My prefix here is `{current}`. You can always mention me instead."
            ))
            return

        if ctx.author.id != ctx.guild.owner_id and not await self.bot.is_owner(ctx.author):
            await ctx.send(embed=embeds.error("Only the server owner can change the prefix."))
            return

        new = new.strip()
        if not new or len(new) > _MAX_PREFIX_LEN or any(c.isspace() for c in new):
            await ctx.send(embed=embeds.error(
                f"Prefix must be 1-{_MAX_PREFIX_LEN} characters with no spaces."
            ))
            return

        await service.set_prefix(ctx.guild.id, new)
        await ctx.send(embed=embeds.success(
            f"Prefix set to `{new}`. Mentioning me still works too."
        ))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Prefix(bot))
