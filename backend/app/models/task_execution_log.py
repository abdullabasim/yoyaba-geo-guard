"""TaskExecutionLog — the audit trail behind the System Task Monitor page.

Every Celery task writes a PENDING row before doing work and updates it to
SUCCESS / FAILED / SKIPPED afterwards, so a crashed worker leaves a visible
PENDING row rather than no trace at all.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum as SAEnum, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import TaskStatus

# Postgres has no practical limit here, but unbounded tracebacks make the
# monitor table unusable and bloat the row.
MAX_ERROR_MESSAGE_LENGTH = 4000


class TaskExecutionLog(Base):
    __tablename__ = "task_execution_logs"
    __table_args__ = (
        Index("ix_task_logs_started_desc", "started_at"),
        Index("ix_task_logs_status_started", "status", "started_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    task_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    target_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    keyword_text: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[TaskStatus] = mapped_column(
        SAEnum(TaskStatus, name="task_status", native_enum=True, validate_strings=True, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=TaskStatus.PENDING,
        server_default=TaskStatus.PENDING.value,
        index=True,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Celery's own task id, so a log row can be correlated with worker output.
    celery_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    # Arbitrary diagnostic context (ids, ranks, provider cost, timings).
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<TaskExecutionLog id={self.id} task={self.task_name!r} status={self.status}>"
