"""AI alert schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import IssueType
from app.schemas.common import ORMModel


class AIAlertResponse(ORMModel):
    id: int
    history_id: int
    issue_type: IssueType
    ai_diagnosis: str
    actionable_advice: str
    confidence: float | None
    competitor_signals: list[dict] | None
    model_used: str | None
    slack_sent: bool
    created_at: datetime


class AIAlertDetail(AIAlertResponse):
    """Alert joined with the observation and entity names it belongs to."""

    keyword_text: str | None = None
    url: str | None = None
    project_name: str | None = None
    client_name: str | None = None
    current_rank: int | None = None
    previous_rank: int | None = None
    check_date: datetime | None = None


class AIAlertStats(BaseModel):
    total: int = 0
    by_issue_type: dict[str, int] = Field(default_factory=dict)
    unsent: int = 0
    window_days: int = 30
