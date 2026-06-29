"""Scaffold a new vertical-slice module the way the existing ones are built.

    uv run python scripts/new_module.py <name>

Generates a complete, loadable, tested slice: a per-guild Config model, repository,
discord-free service (cached config + set_enabled), a manage_guild ``,<name>`` cog
(enable / disable / status) that registers a ``,setup <name>`` panel, the WizardView
panel, and a test. It also registers the model in ``src/database/models/__init__.py``.

After running:
    uv run alembic revision --autogenerate -m "add <name> tables"
    uv run alembic upgrade head
    uv run ruff check --fix src/modules/<name> src/database/models/<name>.py
and optionally add "<Name>" to a bucket in src/modules/help/categories.py
(an unlisted cog falls into the Utility default automatically).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Templates use %name% (lowercase), %Name% (PascalCase cog/class), %Title% (display)
# so the literal { } of f-strings/dicts inside them are left untouched.
_MODEL = '''\
"""%Title% state.

NOTE: adds the %name%_config table; run an Alembic migration (autogenerate).
"""

from __future__ import annotations

from sqlalchemy import BigInteger, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base, TimestampMixin


class %Name%Config(Base, TimestampMixin):
    """Per-guild %name% settings (one row per guild)."""

    __tablename__ = "%name%_config"

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
'''

_REPO = '''\
"""Data access for %name%, mirroring src/modules/leveling/repository.py."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models.%name% import %Name%Config


class %Name%Repository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_config(self, guild_id: int) -> %Name%Config | None:
        return await self.session.get(%Name%Config, guild_id)

    async def get_or_create_config(self, guild_id: int) -> %Name%Config:
        cfg = await self.session.get(%Name%Config, guild_id)
        if cfg is None:
            cfg = %Name%Config(guild_id=guild_id)
            self.session.add(cfg)
            await self.session.flush()
        return cfg
'''

_SERVICE = '''\
"""%Title% logic. No discord here: the cog does the Discord work."""

from __future__ import annotations

from src.core.cache import TTLCache
from src.database.session import get_session
from src.modules.%name%.repository import %Name%Repository

_NO_CONFIG = object()
_config_cache: TTLCache = TTLCache(ttl_seconds=300)


async def get_config(guild_id: int):
    cached = _config_cache.get(guild_id)
    if cached is not None:
        return None if cached is _NO_CONFIG else cached
    async with get_session() as session:
        cfg = await %Name%Repository(session).get_config(guild_id)
    _config_cache.set(guild_id, cfg if cfg is not None else _NO_CONFIG)
    return cfg


async def set_enabled(guild_id: int, value: bool) -> None:
    async with get_session() as session:
        (await %Name%Repository(session).get_or_create_config(guild_id)).enabled = value
    _config_cache.invalidate(guild_id)
'''

_COG = '''\
"""%Title%: TODO describe what this module does."""

from __future__ import annotations

from discord.ext import commands

from src.core import embeds
from src.core.emojis import Emojis
from src.core.paginator import send_command_browser
from src.modules.%name% import service


class %Name%(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        from src.core.setup_registry import SetupEntry, register_setup
        from src.modules.%name%.setup_view import %Name%SetupView

        register_setup(SetupEntry(
            key="%name%", label="%Title%", emoji=Emojis.SETTINGS,
            description="Configure %name% for your server.",
            factory=lambda author_id, guild_id: %Name%SetupView(author_id, guild_id),
        ))

    def cog_unload(self) -> None:
        from src.core.setup_registry import unregister_setup

        unregister_setup("%name%")

    @commands.group(name="%name%", invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def %name%(self, ctx: commands.Context) -> None:
        """Configure %name% for this server."""
        await send_command_browser(ctx, ctx.command)

    @%name%.command(name="enable")
    @commands.has_permissions(manage_guild=True)
    async def %name%_enable(self, ctx: commands.Context) -> None:
        """Turn %name% on."""
        await service.set_enabled(ctx.guild.id, True)
        await ctx.send(embed=embeds.success("%Title% enabled."))

    @%name%.command(name="disable")
    @commands.has_permissions(manage_guild=True)
    async def %name%_disable(self, ctx: commands.Context) -> None:
        """Turn %name% off."""
        await service.set_enabled(ctx.guild.id, False)
        await ctx.send(embed=embeds.success("%Title% disabled."))

    @%name%.command(name="status")
    @commands.has_permissions(manage_guild=True)
    async def %name%_status(self, ctx: commands.Context) -> None:
        """Show this server's %name% configuration."""
        cfg = await service.get_config(ctx.guild.id)
        e = embeds.info("", f"{Emojis.SETTINGS} %Title%")
        e.add_field(name="Status", value="On" if (cfg and cfg.enabled) else "Off")
        await ctx.send(embed=e)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(%Name%(bot))
'''

_SETUP_VIEW = '''\
"""The ,setup %name% panel."""

from __future__ import annotations

import discord

from src.core import embeds
from src.core.emojis import Emojis
from src.core.views import WizardView
from src.modules.%name% import service


class %Name%SetupView(WizardView):
    def __init__(self, author_id: int, guild_id: int) -> None:
        super().__init__(author_id)
        self.guild_id = guild_id
        self._cfg = None

    @property
    def _enabled(self) -> bool:
        return bool(self._cfg and self._cfg.enabled)

    async def load(self) -> None:
        self._cfg = await service.get_config(self.guild_id)
        self._sync()

    def _sync(self) -> None:
        self._enabled_btn.label = f"%Title%: {'On' if self._enabled else 'Off'}"
        self._enabled_btn.style = (
            discord.ButtonStyle.success if self._enabled else discord.ButtonStyle.secondary
        )

    def render(self) -> discord.Embed:
        e = embeds.info("", f"{Emojis.SETTINGS} %Title% Setup")
        e.add_field(name="Status", value="On" if self._enabled else "Off")
        return self._stamp(e)

    @discord.ui.button(label="%Title%: Off", style=discord.ButtonStyle.secondary, row=0)
    async def _enabled_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await service.set_enabled(self.guild_id, not self._enabled)
        await self.refresh(interaction)

    @discord.ui.button(label="Done", emoji=Emojis.SUCCESS, style=discord.ButtonStyle.success, row=1)
    async def _done_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(
            embed=embeds.success("%Title% setup saved.", "Done"), view=self
        )
        self.stop()

    @discord.ui.button(label="Close", emoji=Emojis.CLOSE, style=discord.ButtonStyle.danger, row=1)
    async def _close_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await interaction.response.defer()
        try:
            await interaction.message.delete()
        except discord.HTTPException:
            pass
        self.stop()
'''

_TEST = '''\
"""Tests for the ,setup %name% panel."""

from __future__ import annotations

from types import SimpleNamespace

import discord

from src.modules.%name%.setup_view import %Name%SetupView


def test_panel_layout():
    view = %Name%SetupView(1, 100)
    labels = {c.label for c in view.children if isinstance(c, discord.ui.Button)}
    assert labels == {"%Title%: Off", "Done", "Close"}


def test_render_default_off():
    view = %Name%SetupView(1, 100)
    assert view.render().fields[0].value == "Off"


class _FakeResponse:
    def __init__(self) -> None:
        self.sent = None

    async def send_message(self, *args, **kwargs) -> None:
        self.sent = (args, kwargs)


async def test_only_invoker_may_use_panel():
    view = %Name%SetupView(1, 100)
    intruder = SimpleNamespace(user=SimpleNamespace(id=2), response=_FakeResponse())
    assert await view.interaction_check(intruder) is False
'''


def _render(template: str, name: str, klass: str, title: str) -> str:
    return template.replace("%name%", name).replace("%Name%", klass).replace("%Title%", title)


def _register_model(name: str, klass: str) -> None:
    """Insert the model import + __all__ entry into models/__init__.py."""
    path = ROOT / "src" / "database" / "models" / "__init__.py"
    text = path.read_text(encoding="utf-8")
    import_line = f"from src.database.models.{name} import {klass}Config\n"
    if import_line in text:
        return
    text = text.replace("\n__all__ = [", f"{import_line}\n__all__ = [", 1)
    close = text.rfind("\n]")
    text = text[:close] + f'\n    "{klass}Config",' + text[close:]
    path.write_text(text, encoding="utf-8")


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("usage: uv run python scripts/new_module.py <name>")
    raw = sys.argv[1]
    name = re.sub(r"[^a-z0-9]", "", raw.lower())
    if not name or not name[0].isalpha():
        sys.exit(f"invalid module name: {raw!r} (use letters/digits, start with a letter)")
    klass = name.capitalize()
    title = name.capitalize()

    module_dir = ROOT / "src" / "modules" / name
    if module_dir.exists():
        sys.exit(f"module already exists: {module_dir}")

    files = {
        ROOT / "src" / "database" / "models" / f"{name}.py": _MODEL,
        module_dir / "__init__.py": "",
        module_dir / "repository.py": _REPO,
        module_dir / "service.py": _SERVICE,
        module_dir / "cog.py": _COG,
        module_dir / "setup_view.py": _SETUP_VIEW,
        ROOT / "tests" / f"test_{name}.py": _TEST,
    }
    module_dir.mkdir(parents=True)
    for path, template in files.items():
        path.write_text(_render(template, name, klass, title), encoding="utf-8")
    _register_model(name, klass)

    print(f"Scaffolded module '{name}' ({klass}). Next:")
    print(f"  uv run alembic revision --autogenerate -m 'add {name} tables'")
    print("  uv run alembic upgrade head")
    print(f"  uv run ruff check --fix src/modules/{name} src/database/models/{name}.py")
    print(f"  (optional) add \"{klass}\" to a bucket in src/modules/help/categories.py")


if __name__ == "__main__":
    main()
