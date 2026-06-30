"""add players.tos_accepted_at (economy rules agreement)

Revision ID: d1a2b3c4e5f6
Revises: c0ffee5a1b2c
Create Date: 2026-06-29 12:10:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'd1a2b3c4e5f6'
down_revision: str | None = 'c0ffee5a1b2c'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'players',
        sa.Column('tos_accepted_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('players', 'tos_accepted_at')
