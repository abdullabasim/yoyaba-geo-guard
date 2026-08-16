"""Task execution log schemas (System Task Monitor)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.models.enums import TaskStatus
from app.schemas.common import ORMModel


class TaskExecutionLogResponse(ORMModel):
    id: int
    task_name: str
    target_url: str | None
    keyword_text: str | None
    status: TaskStatus
    error_message: str | None
    celery_task_id: str | None
    payload: dict | None
    duration_ms: int | None
    started_at: datetime
    completed_at: datetime | None


class TaskStatsResponse(BaseModel):
    """Counters for the monitor page header badges."""

    pending: int = 0
    success: int = 0
    failed: int = 0
    skipped: int = 0
    total: int = 0
    window_hours: int = 24


class ManualRunRequest(BaseModel):
    """Trigger an immediate check outside the schedule."""

    target_url_id: int
    keyword_id: int | None = None
    force_analysis: bool = False


class ManualRunResponse(BaseModel):
    dispatched: int
    celery_task_ids: list[str]
