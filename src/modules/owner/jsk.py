"""On-brand jishaku: a themed ,jsk overview that says what each command does.

Stock jishaku's bare ``,jsk`` prints a plain-text diagnostic block and never
explains its subcommands. We subclass it and override only the root command to
render a house-style embed — a short runtime summary plus a labelled catalog of
what jsk can do. Everything else (eval, shell, reload, sync, …) is inherited
untouched, so behavior is identical to stock jishaku.

Loaded from ``core/bot.py`` in place of the stock ``jishaku`` extension. That
loader falls back to stock jishaku if anything here fails, so a jishaku API change
can never keep the bot from starting — it just loses the theming.
"""

from __future__ import annotations

import sys

import discord
import jishaku
from discord.ext import commands
from jishaku.cog import OPTIONAL_FEATURES, STANDARD_FEATURES
from jishaku.features.baseclass import Feature

from src.core import embeds
from src.core.emojis import Emojis

# What each jsk command does, grouped for the overview. Kept here (not scraped
# from jishaku) so the wording is ours and stable across jishaku versions.
_SECTIONS: list[tuple[str, list[tuple[str, str]]]] = [
    ("Evaluate", [
        ("py <code>", "Run Python in an async scope (`_` is the last result)."),
        ("py_inspect <code>", "Run Python and inspect the result object."),
        ("dis <code>", "Disassemble Python to bytecode."),
        ("sh <cmd>", "Run a shell command with live streaming output."),
        ("git <args> · pip <args>", "Shell shortcuts for git and pip."),
    ]),
    ("Bot & extensions", [
        ("load / unload / reload [ext…]", "Manage cogs (`~` = the invoking one)."),
        ("sync [guild…]", "Sync application (slash) commands."),
        ("shutdown", "Log out and close the bot."),
    ]),
    ("Run & inspect", [
        ("invoke <cmd> · debug <cmd>", "Run a command, or run it and time/trace it."),
        ("repeat <n> <cmd>", "Invoke a command n times."),
        ("su <user> <cmd> · sudo <cmd>", "Run as another user, or bypass checks."),
        ("rtt", "Measure message round-trip latency."),
        ("cat <file> · curl <url>", "Read a file, or fetch a URL."),
        ("tasks · cancel <n>", "List or cancel running eval tasks."),
        ("hide · show", "Hide or reveal jishaku in the help command."),
    ]),
]


class ThemedJishaku(*OPTIONAL_FEATURES, *STANDARD_FEATURES, name="Jishaku"):  # type: ignore[misc]
    """Stock jishaku with a themed root command."""

    @Feature.Command(name="jishaku", aliases=["jsk"], invoke_without_command=True,
                     ignore_extra=False)
    async def jsk(self, ctx: commands.Context) -> None:
        """The jishaku dev toolkit. Run a subcommand, e.g. ,jsk py 1+1."""
        summary = (
            f"Python `{sys.version.split()[0]}` · "
            f"discord.py `{discord.__version__}` · "
            f"jishaku `{jishaku.__version__}`\n"
            f"Watching **{len(self.bot.guilds)}** servers · "
            f"**{len(self.bot.users)}** users · "
            f"`{self.bot.latency * 1000:.0f}ms` gateway"
        )
        e = embeds.info(summary, f"{Emojis.SETTINGS} Jishaku dev toolkit")
        p = ctx.clean_prefix
        for name, rows in _SECTIONS:
            value = "\n".join(f"`{p}jsk {usage}` · {desc}" for usage, desc in rows)
            e.add_field(name=name, value=value, inline=False)
        e.set_footer(text="Owner only · everything here runs with full bot privileges")
        await ctx.send(embed=e)


async def setup(bot) -> None:
    await bot.add_cog(ThemedJishaku(bot=bot))
