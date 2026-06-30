"""Permission gating for the emoji and sticker (expressions) cogs.

Behavioral: these run each command's actual checks against a fake context and
assert that the management commands raise MissingPermissions for a member
lacking ``manage_expressions`` — guarding against the escalation bug where
rename/remove had no permission decorator — while the read-only commands stay
open to everyone.
"""

from __future__ import annotations

from types import SimpleNamespace

import discord
import pytest
from discord.ext import commands

from src.modules.emoji.cog import Emoji
from src.modules.sticker.cog import Sticker


def _ctx(*, can_manage: bool) -> SimpleNamespace:
    """A fake context whose member/bot permissions allow everything except,
    optionally, ``manage_expressions``."""
    perms = discord.Permissions.all()
    perms.manage_expressions = can_manage
    return SimpleNamespace(permissions=perms, bot_permissions=perms)


async def _run_checks(cmd: commands.Command, ctx: SimpleNamespace) -> None:
    for predicate in cmd.checks:
        result = predicate(ctx)
        if hasattr(result, "__await__"):
            result = await result


MANAGED = [
    (Emoji, "emoji_add"),
    (Emoji, "emoji_rename"),
    (Emoji, "emoji_remove"),
    (Sticker, "sticker_add"),
    (Sticker, "sticker_rename"),
    (Sticker, "sticker_remove"),
]

OPEN = [
    (Emoji, "emoji_enlarge"),
    (Emoji, "emoji_list"),
    (Sticker, "sticker_list"),
]


@pytest.mark.parametrize(("cog_cls", "cmd_name"), MANAGED)
async def test_management_commands_require_manage_expressions(cog_cls, cmd_name):
    cmd = getattr(cog_cls(None), cmd_name)
    # A member without manage_expressions is rejected.
    with pytest.raises(commands.MissingPermissions):
        await _run_checks(cmd, _ctx(can_manage=False))
    # A member with it passes every check.
    await _run_checks(cmd, _ctx(can_manage=True))


@pytest.mark.parametrize(("cog_cls", "cmd_name"), OPEN)
async def test_readonly_commands_have_no_permission_gate(cog_cls, cmd_name):
    cmd = getattr(cog_cls(None), cmd_name)
    await _run_checks(cmd, _ctx(can_manage=False))
