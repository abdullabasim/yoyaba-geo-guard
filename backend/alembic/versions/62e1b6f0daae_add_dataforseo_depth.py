"""add_dataforseo_depth

Revision ID: 62e1b6f0daae
Revises: 0003_add_rank_drop_threshold
Create Date: 2026-08-15 22:17:22.430617

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '62e1b6f0daae'
down_revision: Union[str, None] = '0003_add_rank_drop_threshold'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column(
            "dataforseo_depth",
            sa.Integer(),
            server_default="10",
            nullable=False,
        ),
    )
    op.add_column(
        "target_urls",
        sa.Column(
            "dataforseo_depth",
            sa.Integer(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("target_urls", "dataforseo_depth")
    op.drop_column("projects", "dataforseo_depth")
