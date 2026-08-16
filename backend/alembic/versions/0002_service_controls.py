"""service controls, project schedule defaults, url schedule inheritance

Adds:
* ``service_controls`` — one row per pausable subsystem, read by the worker on
  every task so a switch takes effect without a restart.
* ``projects.default_check_interval`` / ``default_execution_time`` /
  ``default_timezone`` — project-level schedule defaults.
* ``target_urls.inherit_schedule`` — whether a URL follows its project's default
  or keeps its own schedule.

Backfill note: existing URLs are set to ``inherit_schedule = false``. They were
created with explicit per-URL schedules, and silently re-pointing them at a
project default would move their execution time without anyone asking.

Revision ID: 0002_service_controls
Revises: 0001_initial
Create Date: 2026-08-15

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0002_service_controls"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SERVICE_KEYS = (
    "SCHEDULER",
    "SERP_FETCH",
    "AI_ANALYSIS",
    "SLACK_ALERTS",
    "ERROR_ALERTS",
    "HEALTH_MONITOR",
)

service_key_enum = postgresql.ENUM(*SERVICE_KEYS, name="service_key", create_type=False)

# Reuses the type created by 0001; must not attempt to create it again.
check_interval_enum = postgresql.ENUM(
    "daily", "weekly", "monthly", name="check_interval", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    service_key_enum.create(bind, checkfirst=True)

    # ---------------------------------------------------------------
    # service_controls
    # ---------------------------------------------------------------
    op.create_table(
        "service_controls",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("service_key", service_key_enum, nullable=False),
        sa.Column("is_enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("paused_reason", sa.Text(), nullable=True),
        sa.Column("paused_by", sa.String(length=320), nullable=True),
        sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_service_controls_service_key",
        "service_controls",
        ["service_key"],
        unique=True,
    )

    # Seed every switch as enabled. A missing row must never be the reason work
    # silently stops, so the application also treats "absent" as enabled.
    op.execute(
        sa.text(
            "INSERT INTO service_controls (service_key, is_enabled) "
            "SELECT unnest(ARRAY['SCHEDULER','SERP_FETCH','AI_ANALYSIS',"
            "'SLACK_ALERTS','ERROR_ALERTS','HEALTH_MONITOR']::service_key[]), true"
        )
    )

    # ---------------------------------------------------------------
    # projects: schedule defaults
    # ---------------------------------------------------------------
    op.add_column(
        "projects",
        sa.Column(
            "default_check_interval",
            check_interval_enum,
            server_default="daily",
            nullable=False,
        ),
    )
    op.add_column(
        "projects",
        sa.Column(
            "default_execution_time",
            sa.Time(timezone=False),
            server_default="03:00:00",
            nullable=False,
        ),
    )
    op.add_column(
        "projects",
        sa.Column(
            "default_timezone",
            sa.String(length=64),
            server_default="UTC",
            nullable=False,
        ),
    )

    # ---------------------------------------------------------------
    # target_urls: schedule inheritance
    # ---------------------------------------------------------------
    op.add_column(
        "target_urls",
        sa.Column(
            "inherit_schedule",
            sa.Boolean(),
            server_default="true",
            nullable=False,
        ),
    )
    op.create_index(
        "ix_target_urls_inherit_schedule", "target_urls", ["inherit_schedule"]
    )

    # Existing rows keep the schedule they already had.
    op.execute(sa.text("UPDATE target_urls SET inherit_schedule = false"))

    # Give each project a default derived from its URLs, so switching a URL to
    # inherit later lands on something sensible rather than a blank 03:00 UTC.
    op.execute(
        sa.text(
            """
            UPDATE projects p
            SET default_execution_time = sub.execution_time,
                default_timezone = sub.timezone,
                default_check_interval = sub.check_interval
            FROM (
                SELECT DISTINCT ON (project_id)
                       project_id, execution_time, timezone, check_interval
                FROM target_urls
                ORDER BY project_id, id
            ) AS sub
            WHERE p.id = sub.project_id
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_target_urls_inherit_schedule", table_name="target_urls")
    op.drop_column("target_urls", "inherit_schedule")

    op.drop_column("projects", "default_timezone")
    op.drop_column("projects", "default_execution_time")
    op.drop_column("projects", "default_check_interval")

    op.drop_index("ix_service_controls_service_key", table_name="service_controls")
    op.drop_table("service_controls")

    service_key_enum.drop(op.get_bind(), checkfirst=True)
