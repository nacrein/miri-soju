"""Data access for automod: the config row and the four child-list tables."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models.automod import (
    AutomodConfig,
    AutomodDomain,
    AutomodExemptChannel,
    AutomodExemptRole,
    AutomodWord,
)


class AutomodRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ── config ────────────────────────────────────────────────────────────────

    async def get_config(self, guild_id: int) -> Optional[AutomodConfig]:
        return await self.session.get(AutomodConfig, guild_id)

    async def get_or_create_config(self, guild_id: int) -> AutomodConfig:
        cfg = await self.session.get(AutomodConfig, guild_id)
        if cfg is None:
            cfg = AutomodConfig(guild_id=guild_id)
            self.session.add(cfg)
            await self.session.flush()
        return cfg

    # ── generic child-list helpers ─────────────────────────────────────────────

    async def _add(self, model, **vals) -> bool:
        """Insert a child row unless an identical one exists. True if newly added."""
        stmt = select(model).where(*[getattr(model, k) == v for k, v in vals.items()])
        if (await self.session.execute(stmt)).scalar_one_or_none() is not None:
            return False
        self.session.add(model(**vals))
        return True

    async def _remove(self, model, **vals) -> bool:
        stmt = delete(model).where(*[getattr(model, k) == v for k, v in vals.items()])
        return ((await self.session.execute(stmt)).rowcount or 0) > 0

    async def _list(self, model, column, guild_id: int) -> list:
        stmt = select(column).where(model.guild_id == guild_id).order_by(column.asc())
        return [r[0] for r in (await self.session.execute(stmt)).all()]

    # ── words ───────────────────────────────────────────────────────────────────
    async def add_word(self, guild_id: int, word: str) -> bool:
        return await self._add(AutomodWord, guild_id=guild_id, word=word)

    async def remove_word(self, guild_id: int, word: str) -> bool:
        return await self._remove(AutomodWord, guild_id=guild_id, word=word)

    async def list_words(self, guild_id: int) -> list[str]:
        return await self._list(AutomodWord, AutomodWord.word, guild_id)

    # ── domains (allowlist) ─────────────────────────────────────────────────────
    async def add_domain(self, guild_id: int, domain: str) -> bool:
        return await self._add(AutomodDomain, guild_id=guild_id, domain=domain)

    async def remove_domain(self, guild_id: int, domain: str) -> bool:
        return await self._remove(AutomodDomain, guild_id=guild_id, domain=domain)

    async def list_domains(self, guild_id: int) -> list[str]:
        return await self._list(AutomodDomain, AutomodDomain.domain, guild_id)

    # ── exempt roles ────────────────────────────────────────────────────────────
    async def add_exempt_role(self, guild_id: int, role_id: int) -> bool:
        return await self._add(AutomodExemptRole, guild_id=guild_id, role_id=role_id)

    async def remove_exempt_role(self, guild_id: int, role_id: int) -> bool:
        return await self._remove(AutomodExemptRole, guild_id=guild_id, role_id=role_id)

    async def list_exempt_roles(self, guild_id: int) -> list[int]:
        return await self._list(AutomodExemptRole, AutomodExemptRole.role_id, guild_id)

    # ── exempt channels ─────────────────────────────────────────────────────────
    async def add_exempt_channel(self, guild_id: int, channel_id: int) -> bool:
        return await self._add(AutomodExemptChannel, guild_id=guild_id, channel_id=channel_id)

    async def remove_exempt_channel(self, guild_id: int, channel_id: int) -> bool:
        return await self._remove(AutomodExemptChannel, guild_id=guild_id, channel_id=channel_id)

    async def list_exempt_channels(self, guild_id: int) -> list[int]:
        return await self._list(AutomodExemptChannel, AutomodExemptChannel.channel_id, guild_id)
