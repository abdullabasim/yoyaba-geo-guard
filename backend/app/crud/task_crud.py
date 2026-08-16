"""TaskExecutionLog CRUD.

Log writes must never be the reason a task fails, so callers treat these as
best-effort. The task wrapper in ``app.worker.logging_ctx`` handles that.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import TaskStatus
from app.models.task_execution_log import (
    MAX_ERROR_MESSAGE_LENGTH,
    TaskExecutionLog,
)
from app.schemas.task_schema import TaskStatsResponse


class CRUDTaskLog:
    async def get(self, session: AsyncSession, log_id: int) -> TaskExecutionLog | None:
        return await session.get(TaskExecutionLog, log_id)

    async def start(
        self,
        session: AsyncSession,
        *,
        task_name: str,
        target_url: str | None = None,
        keyword_text: str | None = None,
        celery_task_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> TaskExecutionLog:
        row = TaskExecutionLog(
            task_name=task_name,
            target_url=target_url,
            keyword_text=keyword_text,
            celery_task_id=celery_task_id,
            payload=payload,
            status=TaskStatus.PENDING,
            started_at=datetime.now(UTC),
        )
        session.add(row)
        await session.flush()
        await session.refresh(row)
        return row

    async def finish(
        self,
        session: AsyncSession,
        log_id: int,
        *,
        status: TaskStatus,
        error_message: str | None = None,
        target_url: str | None = None,
        keyword_text: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        row = await session.get(TaskExecutionLog, log_id)
        if row is None:
            return

        completed = datetime.now(UTC)
        started = row.started_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=UTC)

        row.status = status
        row.completed_at = completed
        row.duration_ms = int((completed - started).total_seconds() * 1000)
        if target_url:
            row.target_url = target_url
        if keyword_text:
            row.keyword_text = keyword_text
        if error_message is not None:
            row.error_message = error_message[:MAX_ERROR_MESSAGE_LENGTH]
        if payload is not None:
            merged = dict(row.payload or {})
            merged.update(payload)
            row.payload = merged
        session.add(row)
        await session.flush()

    async def list_recent(
        self,
        session: AsyncSession,
        *,
        status: TaskStatus | None = None,
        task_name: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[TaskExecutionLog]:
        stmt = select(TaskExecutionLog).order_by(TaskExecutionLog.started_at.desc())
        if status is not None:
            stmt = stmt.where(TaskExecutionLog.status == status)
        if task_name:
            stmt = stmt.where(TaskExecutionLog.task_name == task_name)
        result = await session.execute(stmt.offset(skip).limit(limit))
        return list(result.scalars().all())

    async def count(
        self,
        session: AsyncSession,
        *,
        status: TaskStatus | None = None,
        task_name: str | None = None,
    ) -> int:
        stmt = select(func.count()).select_from(TaskExecutionLog)
        if status is not None:
            stmt = stmt.where(TaskExecutionLog.status == status)
        if task_name:
            stmt = stmt.where(TaskExecutionLog.task_name == task_name)
        result = await session.execute(stmt)
        return int(result.scalar_one())

    async def get_stats(
        self, session: AsyncSession, *, window_hours: int = 24
    ) -> TaskStatsResponse:
        since = datetime.now(UTC) - timedelta(hours=window_hours)
        result = await session.execute(
            select(TaskExecutionLog.status, func.count())
            .where(TaskExecutionLog.started_at >= since)
            .group_by(TaskExecutionLog.status)
        )
        counts = {status: int(count) for status, count in result.all()}
        return TaskStatsResponse(
            pending=counts.get(TaskStatus.PENDING, 0),
            success=counts.get(TaskStatus.SUCCESS, 0),
            failed=counts.get(TaskStatus.FAILED, 0),
            skipped=counts.get(TaskStatus.SKIPPED, 0),
            total=sum(counts.values()),
            window_hours=window_hours,
        )


task_log_crud = CRUDTaskLog()
