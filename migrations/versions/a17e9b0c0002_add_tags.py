"""add tags table

Revision ID: a17e9b0c0002
Revises: a17e9b0c0001
Create Date: 2026-06-30 09:05:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'a17e9b0c0002'
down_revision: str | None = 'a17e9b0c0001'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'tags',
        sa.Column('guild_id', sa.BigInteger(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('content', sa.String(length=2000), nullable=False),
        sa.Column('author_id', sa.BigInteger(), nullable=False),
        sa.Column('uses', sa.Integer(), nullable=False),
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
        sa.UniqueConstraint('guild_id', 'name', name='uq_tag_guild_name'),
    )
    op.create_index('ix_tag_guild_name', 'tags', ['guild_id', 'name'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_tag_guild_name', table_name='tags')
    op.drop_table('tags')
