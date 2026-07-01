"""merge command_usage and feature migration heads

Revision ID: e15584a04a9d
Revises: a17e9b0c0006, e2f3a4b5c6d7
Create Date: 2026-07-01 07:07:56.006188
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e15584a04a9d'
down_revision: Union[str, None] = ('a17e9b0c0006', 'e2f3a4b5c6d7')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
