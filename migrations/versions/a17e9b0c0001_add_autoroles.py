"""add auto_roles table

Revision ID: a17e9b0c0001
Revises: d1a2b3c4e5f6
Create Date: 2026-06-30 09:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'a17e9b0c0001'
down_revision: str | None = 'd1a2b3c4e5f6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'auto_roles',
        sa.Column('guild_id', sa.BigInteger(), nullable=False),
        sa.Column('role_id', sa.BigInteger(), nullable=False),
        sa.Column(
            'id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'),
            autoincrement=True, nullable=False,
        ),
        sa.Column(
            'created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            'updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('guild_id', 'role_id', name='uq_autorole_guild_role'),
    )
    op.create_index('ix_autorole_guild', 'auto_roles', ['guild_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_autorole_guild', table_name='auto_roles')
    op.drop_table('auto_roles')
