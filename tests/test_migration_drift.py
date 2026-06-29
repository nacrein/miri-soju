"""Migration drift guard: every model must be represented in the Alembic migrations.

Applies all migrations to a throwaway SQLite DB, reflects it, and asserts every table
and column the live models define actually exists. A new model (or column) with no
migration — the class of bug that caused the `7187AE` "missing table" outage — fails
here in CI instead of breaking at runtime in production.

This is a sync test on purpose: ``alembic.command.upgrade`` runs ``asyncio.run`` inside
``migrations/env.py``, which would explode under a running pytest-asyncio loop.
"""

from __future__ import annotations

import os
import tempfile

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

import src.database.models  # noqa: F401 — importing populates Base.metadata
from config.settings import get_settings
from src.database.base import Base


def test_models_match_migrations():
    fd, path = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    posix = path.replace(os.sep, "/")
    old_url = os.environ.get("DATABASE_URL")
    engine = None
    try:
        # Point Alembic (via settings) at the throwaway DB and bring it to head.
        os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{posix}"
        get_settings.cache_clear()
        command.upgrade(Config("alembic.ini"), "head")

        engine = create_engine(f"sqlite:///{posix}")
        insp = inspect(engine)
        db_tables = set(insp.get_table_names())

        missing_tables = sorted(t for t in Base.metadata.tables if t not in db_tables)
        assert not missing_tables, (
            f"Tables defined in models but missing from migrations: {missing_tables}. "
            "Run `uv run alembic revision --autogenerate -m '...'` then `alembic upgrade head`."
        )

        missing_cols: list[str] = []
        for tname, table in Base.metadata.tables.items():
            db_cols = {c["name"] for c in insp.get_columns(tname)}
            missing_cols += [f"{tname}.{c.name}" for c in table.columns if c.name not in db_cols]
        assert not missing_cols, (
            f"Columns defined in models but missing from migrations: {sorted(missing_cols)}. "
            "Generate a new migration for the changed model(s)."
        )
    finally:
        if engine is not None:
            engine.dispose()
        if old_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = old_url
        get_settings.cache_clear()
        os.remove(path)
