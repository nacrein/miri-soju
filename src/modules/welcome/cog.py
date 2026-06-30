"""Welcome & goodbye messages: greet joiners and farewell leavers in a channel.

Templates support {user} (mention), {name} (display name), {server}, and {count}
(member count). Channels and on/off can also be managed from the ,setup welcome panel.
The two commands groups (welcome / goodbye) share one config row per guild."""

from __future__ import annotations

import discord
from discord.ext import commands

from src.core import embeds
from src.core.emojis import Emojis
from src.core.paginator import send_command_browser
from src.modules.welcome import service

_MAX_MESSAGE = 2000
_MENTIONS = discord.AllowedMentions(users=True, roles=False, everyone=False)


def render(template: str, member: discord.Member) -> str:
    """Fill a template's placeholders for a given member."""
    return (
        template.replace("{user}", member.mention)
        .replace("{name}", member.display_name)
        .replace("{server}", member.guild.name)
        .replace("{count}", str(member.guild.member_count or 0))
    )


class Welcome(commands.Cog, name="Welcome"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        from src.core.setup_registry import SetupEntry, register_setup
        from src.modules.welcome.setup_view import WelcomeSetupView

        register_setup(SetupEntry(
            key="welcome", label="Welcome", emoji=Emojis.JOIN,
            description="Greet new members and farewell those who leave.",
            factory=lambda author_id, guild_id: WelcomeSetupView(author_id, guild_id),
        ))

    def cog_unload(self) -> None:
        from src.core.setup_registry import unregister_setup

        unregister_setup("welcome")

    # ── welcome group ───────────────────────────────────────────────────────
    @commands.group(name="welcome", aliases=["greet"], invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def welcome(self, ctx) -> None:
        """Greeting posted when a member joins."""
        await send_command_browser(ctx, ctx.command)

    @welcome.command(name="channel")
    async def welcome_channel(self, ctx, channel: discord.TextChannel) -> None:
        """Set the welcome channel (enables welcomes)."""
        await self._set_channel(ctx, "welcome", channel)

    @welcome.command(name="message", aliases=["msg"])
    async def welcome_message(self, ctx, *, message: str) -> None:
        """Set the welcome text. Placeholders: {user} {name} {server} {count}."""
        await self._set_message(ctx, "welcome", message)

    @welcome.command(name="test")
    async def welcome_test(self, ctx) -> None:
        """Preview the welcome message on yourself."""
        await self._test(ctx, "welcome")

    @welcome.command(name="disable", aliases=["off"])
    async def welcome_disable(self, ctx) -> None:
        """Turn welcomes off."""
        await self._disable(ctx, "welcome")

    # ── goodbye group ───────────────────────────────────────────────────────
    @commands.group(name="goodbye", aliases=["farewell", "leave"], invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def goodbye(self, ctx) -> None:
        """Farewell posted when a member leaves."""
        await send_command_browser(ctx, ctx.command)

    @goodbye.command(name="channel")
    async def goodbye_channel(self, ctx, channel: discord.TextChannel) -> None:
        """Set the goodbye channel (enables goodbyes)."""
        await self._set_channel(ctx, "goodbye", channel)

    @goodbye.command(name="message", aliases=["msg"])
    async def goodbye_message(self, ctx, *, message: str) -> None:
        """Set the goodbye text. Placeholders: {user} {name} {server} {count}."""
        await self._set_message(ctx, "goodbye", message)

    @goodbye.command(name="test")
    async def goodbye_test(self, ctx) -> None:
        """Preview the goodbye message on yourself."""
        await self._test(ctx, "goodbye")

    @goodbye.command(name="disable", aliases=["off"])
    async def goodbye_disable(self, ctx) -> None:
        """Turn goodbyes off."""
        await self._disable(ctx, "goodbye")

    # ── shared handlers ─────────────────────────────────────────────────────
    async def _set_channel(self, ctx, kind: str, channel: discord.TextChannel) -> None:
        await service.set_channel(ctx.guild.id, kind, channel.id)
        await ctx.send(embed=embeds.success(
            f"{kind.title()} messages will post in {channel.mention}."
        ))

    async def _set_message(self, ctx, kind: str, message: str) -> None:
        if len(message) > _MAX_MESSAGE:
            raise commands.BadArgument(f"Message is at most {_MAX_MESSAGE} characters.")
        await service.set_message(ctx.guild.id, kind, message)
        await ctx.send(embed=embeds.success(f"{kind.title()} message updated. Try `,{kind} test`."))

    async def _test(self, ctx, kind: str) -> None:
        summary = await service.get_summary(ctx.guild.id)
        preview = render(summary[kind]["message"], ctx.author)
        if summary[kind]["enabled"] and summary[kind]["channel_id"] is not None:
            await ctx.send(preview, allowed_mentions=_MENTIONS)
        else:
            await ctx.send(embed=embeds.warning(
                f"{kind.title()} is off — preview only:\n\n{preview}"
            ))

    async def _disable(self, ctx, kind: str) -> None:
        await service.set_enabled(ctx.guild.id, kind, False)
        await ctx.send(embed=embeds.success(f"{kind.title()} messages disabled."))

    # ── listeners ───────────────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        await self._fire(member, "welcome")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        await self._fire(member, "goodbye")

    async def _fire(self, member: discord.Member, kind: str) -> None:
        if member.bot:
            return
        resolved = await service.resolve(member.guild.id, kind)
        if resolved is None:
            return
        channel_id, template = resolved
        channel = member.guild.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            return
        try:
            await channel.send(render(template, member), allowed_mentions=_MENTIONS)
        except discord.HTTPException:
            pass


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Welcome(bot))
