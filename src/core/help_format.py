"""Universal command-usage embed. One format for every command's help."""

from __future__ import annotations

import discord
from discord.ext import commands

from src.core import embeds
from src.core.emojis import Emojis

PREFIX = ","


def usage_line(command: commands.Command, prefix: str = PREFIX) -> str:
    """Build `,name <required> [optional]` from the command's signature."""
    parts = [f"{prefix}{command.qualified_name}"]
    for name, param in command.clean_params.items():
        if param.default is param.empty:
            parts.append(f"<{name}>")
        else:
            parts.append(f"[{name}]")
    return " ".join(parts)


def usage_embed(command: commands.Command, prefix: str = PREFIX) -> discord.Embed:
    """The universal per-command help embed."""
    e = embeds.info("", f"{Emojis.INFO} {prefix}{command.qualified_name}")
    e.description = command.help or "No description."

    e.add_field(name="Usage", value=f"`{usage_line(command, prefix)}`", inline=False)

    # Argument breakdown: required vs optional.
    if command.clean_params:
        rows = []
        for name, param in command.clean_params.items():
            tag = "required" if param.default is param.empty else "optional"
            rows.append(f"`{name}` — {tag}")
        e.add_field(name="Arguments", value="\n".join(rows), inline=False)

    # Hand-written example if provided via the command's extras, else the shape.
    example = command.extras.get("example")
    e.add_field(
        name="Example",
        value=f"`{prefix}{example}`" if example else f"`{usage_line(command, prefix)}`",
        inline=False,
    )
    return e
