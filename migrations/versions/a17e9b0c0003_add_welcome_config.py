"""add welcome_config table

Revision ID: a17e9b0c0003
Revises: a17e9b0c0002
Create Date: 2026-06-30 09:10:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'a17e9b0c0003'
down_revision: str | None = 'a17e9b0c0002'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'welcome_config',
        sa.Column('guild_id', sa.BigInteger(), nullable=False),
        sa.Column('welcome_channel_id', sa.BigInteger(), nullable=True),
        sa.Column('welcome_message', sa.String(length=2000), nullable=True),
        sa.Column('welcome_enabled', sa.Boolean(), nullable=False),
        sa.Column('goodbye_channel_id', sa.BigInteger(), nullable=True),
        sa.Column('goodbye_message', sa.String(length=2000), nullable=True),
        sa.Column('goodbye_enabled', sa.Boolean(), nullable=False),
        sa.Column(
            'created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            'updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint('guild_id'),
    )


def downgrade() -> None:
    op.drop_table('welcome_config')
