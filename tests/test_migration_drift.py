"""Migration drift guard: every model must be represented in the Alembic migrations.

Applies all migrations to a throwaway SQLite DB, reflects it, and asserts every table
and column the live models define actually exists — and, crucially, that the indexes,
unique constraints, check constraints, column types and nullability match too. A new
model (or column, index, or constraint) with no migration — the class of bug that caused
the `7187AE` "missing table" outage — fails here in CI instead of breaking at runtime in
production. The economy ``CheckConstraint``s (the final backstop against bad math) and the
``UniqueConstraint``s that enforce one-row-per-guild semantics are exactly the drift this
must guard.

This is a sync test on purpose: ``alembic.command.upgrade`` runs ``asyncio.run`` inside
``migrations/env.py``, which would explode under a running pytest-asyncio loop.
"""

from __future__ import annotations

import os
import tempfile
import warnings
from contextlib import contextmanager

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect
from sqlalchemy.dialects import sqlite
from sqlalchemy.exc import SAWarning
from sqlalchemy.schema import CheckConstraint, Index, UniqueConstraint

import src.database.models  # noqa: F401 — importing populates Base.metadata
from config.settings import get_settings
from src.database.base import Base


@contextmanager
def _migrated_sqlite_inspector():
    """Apply every migration to a throwaway SQLite DB and yield a reflection inspector."""
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
        yield inspect(engine)
    finally:
        if engine is not None:
            engine.dispose()
        if old_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = old_url
        get_settings.cache_clear()
        os.remove(path)


def _is_expression_index(index: Index) -> bool:
    """True for functional/expression indexes (e.g. ``(wallet + vault) DESC``).

    SQLite cannot reflect expression-based indexes (it emits a SAWarning and skips
    them), so they can't be verified by name here; the ``column``-less index is the
    tell. They are still covered by the table-existence and Postgres production paths.
    """
    return not list(index.columns)


def test_models_match_migrations():
    """Tables and columns defined in models must exist in the migration-built schema."""
    with _migrated_sqlite_inspector() as insp:
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


def test_migration_schema_matches_model_constraints_and_types():
    """Indexes, unique/check constraints, column types and nullability must not drift.

    Existence checks (above) miss the most damaging drift classes: a model gaining an
    Index/UniqueConstraint/CheckConstraint — or changing a column's type or nullability —
    with no matching migration would pass silently. Reflect those facets and fail loudly.
    """
    dialect = sqlite.dialect()
    missing_indexes: list[str] = []
    missing_uniques: list[str] = []
    missing_checks: list[str] = []
    type_drift: list[str] = []
    nullable_drift: list[str] = []

    with _migrated_sqlite_inspector() as insp:
        for tname, table in Base.metadata.tables.items():
            # --- column types + nullability ---
            reflected_cols = {c["name"]: c for c in insp.get_columns(tname)}
            for col in table.columns:
                rc = reflected_cols.get(col.name)
                if rc is None:
                    continue  # absence is already caught by test_models_match_migrations
                model_type = col.type.compile(dialect=dialect)
                refl_type = str(rc["type"])
                if model_type != refl_type:
                    type_drift.append(f"{tname}.{col.name}: model={model_type} db={refl_type}")
                if bool(col.nullable) != bool(rc["nullable"]):
                    nullable_drift.append(
                        f"{tname}.{col.name}: model nullable={col.nullable} db={rc['nullable']}"
                    )

            # --- indexes (expression-based ones can't be reflected on SQLite) ---
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", SAWarning)
                db_index_names = {i["name"] for i in insp.get_indexes(tname)}
            for idx in table.indexes:
                if _is_expression_index(idx):
                    continue
                if idx.name not in db_index_names:
                    missing_indexes.append(f"{tname}.{idx.name}")

            # --- named unique + check constraints ---
            db_unique_names = {u["name"] for u in insp.get_unique_constraints(tname)}
            db_check_names = {c["name"] for c in insp.get_check_constraints(tname)}
            for con in table.constraints:
                if isinstance(con, UniqueConstraint) and con.name:
                    if con.name not in db_unique_names:
                        missing_uniques.append(f"{tname}.{con.name}")
                elif isinstance(con, CheckConstraint) and con.name:
                    if con.name not in db_check_names:
                        missing_checks.append(f"{tname}.{con.name}")

    hint = "Generate a new migration for the changed model(s) and `alembic upgrade head`."
    assert not missing_indexes, (
        f"Indexes in models but missing from migrations: {sorted(missing_indexes)}. {hint}"
    )
    assert not missing_uniques, (
        f"Unique constraints in models but missing from migrations: {sorted(missing_uniques)}. {hint}"
    )
    assert not missing_checks, (
        f"Check constraints in models but missing from migrations: {sorted(missing_checks)}. {hint}"
    )
    assert not type_drift, (
        f"Column type drift between models and migrations: {sorted(type_drift)}. {hint}"
    )
    assert not nullable_drift, (
        f"Column nullability drift between models and migrations: {sorted(nullable_drift)}. {hint}"
    )
