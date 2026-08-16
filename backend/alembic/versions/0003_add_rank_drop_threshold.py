"""add rank drop threshold to projects and target_urls

Adds:
* ``projects.rank_drop_threshold`` — project default threshold for AI analysis trigger.
* ``target_urls.rank_drop_threshold`` — per-URL threshold override for AI analysis trigger.

Revision ID: 0003_add_rank_drop_threshold
Revises: 0002_service_controls
Create Date: 2026-08-15

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003_add_rank_drop_threshold"
down_revision: Union[str, None] = "0002_service_controls"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column(
            "rank_drop_threshold",
            sa.Integer(),
            server_default="3",
            nullable=False,
        ),
    )
    op.add_column(
        "target_urls",
        sa.Column(
            "rank_drop_threshold",
            sa.Integer(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("target_urls", "rank_drop_threshold")
    op.drop_column("projects", "rank_drop_threshold")
