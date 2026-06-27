"""Per-command help cards. One template renders every command the same way.

Everything is derived from the live command (its params, help, aliases, and (for
groups) its subcommands), so help never goes stale: a command shows up the moment
it's registered, with its current signature.

This module stays free of feature imports (per the core rule), so anything
feature-specific: the category label, the website link, the invoker shown in the
author row, is passed in by the caller.
"""

from __future__ import annotations

import inspect

import discord
from discord.ext import commands

from src.core import embeds

PREFIX = ","


def usage_line(command: commands.Command, prefix: str = PREFIX) -> str:
    """Build `,name <required> [optional]` straight from the command's signature.

    Required vs optional comes from discord.py's own ``param.required`` (which
    accounts for defaults and ``Optional`` annotations), so the syntax always
    matches how the command actually parses. A variadic ``*arg`` is shown as
    ``<arg…>`` to signal it's repeatable; groups get a trailing ``<subcommand>``.
    """
    parts = [f"{prefix}{command.qualified_name}"]
    for name, param in command.clean_params.items():
        token = f"{name}…" if param.kind is inspect.Parameter.VAR_POSITIONAL else name
        parts.append(f"<{token}>" if param.required else f"[{token}]")
    if isinstance(command, commands.Group):
        parts.append("<subcommand>")
    return " ".join(parts)


def subcommands_of(group: commands.Group) -> list[commands.Command]:
    """A group's visible subcommands, name-sorted."""
    return sorted(
        (c for c in group.commands if not c.hidden),
        key=lambda c: c.qualified_name,
    )


def command_family(command: commands.Command) -> list[commands.Command]:
    """A command followed by all its (visible) subcommands, depth-first.

    This is the page sequence the card pager flips through: `ban`, then
    `ban history`, then `ban list`, … A plain command yields just itself.
    """
    family = [command]
    if isinstance(command, commands.Group):
        for sub in subcommands_of(command):
            family.extend(command_family(sub))
    return family


def command_listing(cmds: list[commands.Command]) -> str:
    """One ansi codeblock naming each top-level command, name-sorted. A group
    shows its visible-subcommand count and a ``..`` marker (``vault (4)..``); a
    plain command is just its name. Used by the help menu so picking a category
    reveals everything in it at once.

    The body is capped so even a very large category fits an embed description.
    """
    parts: list[str] = []
    for c in sorted(cmds, key=lambda c: c.qualified_name):
        if isinstance(c, commands.Group):
            parts.append(f"{c.name} ({len(subcommands_of(c))})..")
        else:
            parts.append(c.name)
    body = ", ".join(parts) if parts else "No commands."
    if len(body) > 3500:  # leave room for the heading/blurb under the 4096 cap
        body = body[:3499] + "…"
    # \x1b is the ANSI escape: 1;36m = bold cyan, 0m resets (Discord ansi block).
    return f"```ansi\n\x1b[1;36m{body}\x1b[0m\n```"


def _ansi_syntax(command: commands.Command, prefix: str) -> str:
    """The ansi Syntax (+ Example) panel: the command path in cyan, each argument
    token in red, so required/optional placeholders pop out at a glance. Groups
    get a trailing ``<subcommand>`` token like any other argument."""
    cyan, red, reset = "\x1b[1;36m", "\x1b[1;31m", "\x1b[0m"
    syntax = f"{cyan}Syntax: {prefix}{command.qualified_name}"
    for name, param in command.clean_params.items():
        token = f"{name}…" if param.kind is inspect.Parameter.VAR_POSITIONAL else name
        wrapped = f"<{token}>" if param.required else f"[{token}]"
        syntax += f" {red}{wrapped}{cyan}"
    if isinstance(command, commands.Group):
        syntax += f" {red}<subcommand>{cyan}"
    lines = [syntax + reset]
    example = command.extras.get("example")
    if example:
        lines.append(f"{cyan}Example: {prefix}{example}{reset}")
    return "```ansi\n" + "\n".join(lines) + "\n```"


def command_card(
    command: commands.Command,
    prefix: str = PREFIX,
    *,
    author: discord.abc.User | None = None,
    category: str | None = None,
    page: int | None = None,
    total: int | None = None,
    url: str | None = None,
) -> discord.Embed:
    """The universal per-command card.

    A markdown ``## Command: name`` heading, the blockquoted help, then an ansi
    Syntax/Example panel. `author` (the invoker) fills the author row; `category`
    + `page`/`total` build the footer (`Moderation • page 1/5 (5 entries)`); `url`
    links the heading. All optional, so the same card works standalone or inside
    the browser.
    """
    title = f"Command: {command.qualified_name}"
    lines = [f"## [{title}]({url})" if url else f"## {title}"]
    help_lines = (command.help or "No description.").splitlines() or ["No description."]
    lines.extend(f"> {line}" for line in help_lines)
    requires = command.extras.get("requires")
    if requires:
        lines.append(requires)
    if command.aliases:
        lines.append("-# Aliases: " + ", ".join(command.aliases))
    lines.append(_ansi_syntax(command, prefix))

    e = discord.Embed(description="\n".join(lines), color=embeds.COLOR_DUSK)
    if author is not None:
        e.set_author(name=author.display_name, icon_url=author.display_avatar.url)

    footer = category or ""
    if page is not None and total is not None:
        paging = f"page {page}/{total} ({total} entries)"
        footer = f"{footer} • {paging}" if footer else paging
    if footer:
        e.set_footer(text=footer)
    return e


def usage_embed(command: commands.Command, prefix: str = PREFIX) -> discord.Embed:
    """Back-compat entry point (used by the global error handler): a standalone
    card with no author row or pager footer."""
    return command_card(command, prefix)
