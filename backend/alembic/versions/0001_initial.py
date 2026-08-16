"""initial schema

Creates the full multi-tenant hierarchy:
    users
    clients -> projects -> target_urls -> keywords -> rankings_history -> ai_alerts
    task_execution_logs (standalone audit trail)

Revision ID: 0001_initial
Revises:
Create Date: 2026-08-15

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


check_interval_enum = postgresql.ENUM(
    "daily", "weekly", "monthly", name="check_interval", create_type=False
)
task_status_enum = postgresql.ENUM(
    "PENDING", "SUCCESS", "FAILED", "SKIPPED", name="task_status", create_type=False
)
issue_type_enum = postgresql.ENUM(
    "INTENT_SHIFT",
    "SERP_FEATURE_CHANGE",
    "NEW_COMPETITOR",
    "CONTENT_FRESHNESS",
    "ALGORITHM_UPDATE",
    "NO_SIGNIFICANT_CHANGE",
    "UNKNOWN",
    name="issue_type",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    check_interval_enum.create(bind, checkfirst=True)
    task_status_enum.create(bind, checkfirst=True)
    issue_type_enum.create(bind, checkfirst=True)

    # ---------------------------------------------------------------
    # users
    # ---------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_superuser", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_is_active", "users", ["is_active"])
    op.create_index("ix_users_created_at", "users", ["created_at"])

    # ---------------------------------------------------------------
    # clients
    # ---------------------------------------------------------------
    op.create_table(
        "clients",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_clients_name", "clients", ["name"])
    op.create_index("ix_clients_is_active", "clients", ["is_active"])
    op.create_index("ix_clients_created_at", "clients", ["created_at"])

    # ---------------------------------------------------------------
    # projects
    # ---------------------------------------------------------------
    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_projects_client_id", "projects", ["client_id"])
    op.create_index("ix_projects_name", "projects", ["name"])
    op.create_index("ix_projects_is_active", "projects", ["is_active"])
    op.create_index("ix_projects_created_at", "projects", ["created_at"])

    # ---------------------------------------------------------------
    # target_urls
    # ---------------------------------------------------------------
    op.create_table(
        "target_urls",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column(
            "check_interval",
            check_interval_enum,
            server_default="daily",
            nullable=False,
        ),
        sa.Column(
            "execution_time",
            sa.Time(timezone=False),
            server_default="03:00:00",
            nullable=False,
        ),
        sa.Column("timezone", sa.String(length=64), server_default="UTC", nullable=False),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_target_urls_project_id", "target_urls", ["project_id"])
    op.create_index("ix_target_urls_url", "target_urls", ["url"])
    op.create_index("ix_target_urls_is_active", "target_urls", ["is_active"])
    op.create_index("ix_target_urls_last_checked_at", "target_urls", ["last_checked_at"])
    op.create_index("ix_target_urls_created_at", "target_urls", ["created_at"])
    op.create_index(
        "ix_target_urls_due_lookup", "target_urls", ["is_active", "execution_time"]
    )

    # ---------------------------------------------------------------
    # keywords
    # ---------------------------------------------------------------
    op.create_table(
        "keywords",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("target_url_id", sa.Integer(), nullable=False),
        sa.Column("keyword_text", sa.String(length=512), nullable=False),
        sa.Column("location_code", sa.Integer(), server_default="2840", nullable=False),
        sa.Column("language_code", sa.String(length=8), server_default="en", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["target_url_id"], ["target_urls.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "target_url_id",
            "keyword_text",
            "location_code",
            "language_code",
            name="uq_keyword_per_url_and_market",
        ),
    )
    op.create_index("ix_keywords_target_url_id", "keywords", ["target_url_id"])
    op.create_index("ix_keywords_keyword_text", "keywords", ["keyword_text"])
    op.create_index("ix_keywords_is_active", "keywords", ["is_active"])
    op.create_index("ix_keywords_created_at", "keywords", ["created_at"])

    # ---------------------------------------------------------------
    # rankings_history
    # ---------------------------------------------------------------
    op.create_table(
        "rankings_history",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("keyword_id", sa.Integer(), nullable=False),
        sa.Column("current_rank", sa.Integer(), nullable=True),
        sa.Column("previous_rank", sa.Integer(), nullable=True),
        sa.Column(
            "top_10_serp_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column("total_results_checked", sa.Integer(), nullable=True),
        sa.Column("serp_url", sa.String(length=2048), nullable=True),
        sa.Column(
            "check_date",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["keyword_id"], ["keywords.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_rankings_history_keyword_id", "rankings_history", ["keyword_id"])
    op.create_index("ix_rankings_history_check_date", "rankings_history", ["check_date"])
    op.create_index(
        "ix_rankings_history_keyword_date",
        "rankings_history",
        ["keyword_id", "check_date"],
    )

    # ---------------------------------------------------------------
    # ai_alerts
    # ---------------------------------------------------------------
    op.create_table(
        "ai_alerts",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("history_id", sa.Integer(), nullable=False),
        sa.Column("issue_type", issue_type_enum, server_default="UNKNOWN", nullable=False),
        sa.Column("ai_diagnosis", sa.Text(), nullable=False),
        sa.Column("actionable_advice", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column(
            "competitor_signals", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("model_used", sa.String(length=128), nullable=True),
        sa.Column("slack_sent", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["history_id"], ["rankings_history.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_ai_alerts_history_id", "ai_alerts", ["history_id"])
    op.create_index("ix_ai_alerts_issue_type", "ai_alerts", ["issue_type"])
    op.create_index("ix_ai_alerts_slack_sent", "ai_alerts", ["slack_sent"])
    op.create_index("ix_ai_alerts_created_at", "ai_alerts", ["created_at"])

    # ---------------------------------------------------------------
    # task_execution_logs
    # ---------------------------------------------------------------
    op.create_table(
        "task_execution_logs",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("task_name", sa.String(length=255), nullable=False),
        sa.Column("target_url", sa.String(length=2048), nullable=True),
        sa.Column("keyword_text", sa.String(length=512), nullable=True),
        sa.Column("status", task_status_enum, server_default="PENDING", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("celery_task_id", sa.String(length=255), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_task_execution_logs_task_name", "task_execution_logs", ["task_name"])
    op.create_index("ix_task_execution_logs_status", "task_execution_logs", ["status"])
    op.create_index(
        "ix_task_execution_logs_celery_task_id", "task_execution_logs", ["celery_task_id"]
    )
    op.create_index("ix_task_logs_started_desc", "task_execution_logs", ["started_at"])
    op.create_index(
        "ix_task_logs_status_started", "task_execution_logs", ["status", "started_at"]
    )


def downgrade() -> None:
    op.drop_table("task_execution_logs")
    op.drop_table("ai_alerts")
    op.drop_table("rankings_history")
    op.drop_table("keywords")
    op.drop_table("target_urls")
    op.drop_table("projects")
    op.drop_table("clients")
    op.drop_table("users")

    bind = op.get_bind()
    issue_type_enum.drop(bind, checkfirst=True)
    task_status_enum.drop(bind, checkfirst=True)
    check_interval_enum.drop(bind, checkfirst=True)
