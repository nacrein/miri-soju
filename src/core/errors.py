"""Global command error handling with short, greppable error IDs."""

from __future__ import annotations

import logging
import uuid

import discord
from discord import app_commands
from discord.ext import commands

from src.core import embeds
from src.core.help_format import usage_embed

log = logging.getLogger(__name__)


class BotError(commands.CommandError):
    """Expected, user-facing error. Its message is shown; not logged as a bug."""


def _new_error_id() -> str:
    """Short uppercase ID, e.g. 'A4F9C2'."""
    return uuid.uuid4().hex[:6].upper()


# User-facing mistakes: friendly message, no error code, not logged as a bug.
_USER_FACING = (
    commands.MissingPermissions,
    commands.BotMissingPermissions,
    commands.MissingRequiredArgument,
    commands.BadArgument,
    commands.CommandOnCooldown,
    commands.NotOwner,
    commands.CheckFailure,
)


def _friendly(exc: Exception) -> str:
    if isinstance(exc, commands.MissingPermissions):
        return "You don't have permission to do that."
    if isinstance(exc, commands.BotMissingPermissions):
        return "I'm missing the permissions to do that."
    if isinstance(exc, commands.MissingRequiredArgument):
        return f"Missing argument: `{exc.param.name}`."
    if isinstance(exc, commands.CommandOnCooldown):
        return f"On cooldown. Try again in {exc.retry_after:.0f}s."
    if isinstance(exc, (commands.NotOwner, commands.CheckFailure)):
        return "You can't use that command."
    return "That didn't work, check your input and try again."


async def _report_bug(send, exc: BaseException, context: str) -> None:
    """Mint an ID, log the traceback under it, tell the user the ID."""
    error_id = _new_error_id()
    log.error("[%s] Unhandled error in %s", error_id, context, exc_info=exc)
    try:
        await send(embed=embeds.error(f"Something went wrong. Error code: `{error_id}`"))
    except discord.HTTPException:
        pass  # if we can't even reply, the log still has it


def setup_error_handling(bot: commands.Bot) -> None:
    """Attach handlers for both prefix and slash command errors."""

    @bot.event
    async def on_command_error(ctx: commands.Context, exc: commands.CommandError) -> None:
        # Unwrap the real exception if it was wrapped during invocation.
        original = getattr(exc, "original", exc)

        if isinstance(exc, commands.CommandNotFound):
            return  # ignore unknown prefix commands silently
        if isinstance(exc, BotError):
            await ctx.send(embed=embeds.error(str(exc)))
            return
        if isinstance(exc, commands.CommandOnCooldown):
            secs = round(exc.retry_after, 1)
            await ctx.send(embed=embeds.error(f"Slow down — try again in {secs}s."))
            return
        if isinstance(exc, commands.MissingRequiredArgument) and ctx.command:
            await ctx.send(embed=usage_embed(ctx.command, ctx.clean_prefix))
            return
        if isinstance(exc, _USER_FACING):
            await ctx.send(embed=embeds.error(_friendly(exc)))
            return
        await _report_bug(ctx.send, original, f"command '{ctx.command}'")

    async def on_app_command_error(
        interaction: discord.Interaction, exc: app_commands.AppCommandError
    ) -> None:
        original = getattr(exc, "original", exc)

        if isinstance(original, BotError):
            msg = str(original)
        elif isinstance(exc, (app_commands.MissingPermissions, app_commands.CheckFailure)):
            msg = "You can't use that command."
        elif isinstance(exc, app_commands.CommandOnCooldown):
            msg = f"On cooldown. Try again in {exc.retry_after:.0f}s."
        else:
            # Real bug: mint an ID and log it.
            error_id = _new_error_id()
            log.error(
                "[%s] Unhandled error in app command '%s'",
                error_id, interaction.command.name if interaction.command else "?",
                exc_info=original,
            )
            msg = f"Something went wrong. Error code: `{error_id}`"

        # Respond whether or not the interaction was already acknowledged.
        embed = embeds.error(msg)
        try:
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)
        except discord.HTTPException:
            pass

    bot.tree.on_error = on_app_command_error
