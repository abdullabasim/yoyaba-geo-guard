"""Project schemas, including project-level schedule defaults."""

from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field, field_validator

from app.models.enums import CheckInterval
from app.schemas.common import ORMModel


def _validate_timezone(value: str) -> str:
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError(f"unknown IANA timezone: {value!r}") from exc
    return value


class ProjectBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    is_active: bool = True
    default_check_interval: CheckInterval = CheckInterval.DAILY
    default_execution_time: time = time(hour=3, minute=0)
    default_timezone: str = "UTC"
    rank_drop_threshold: int = Field(default=3, ge=1, le=50)
    dataforseo_depth: int = Field(default=10, ge=10, le=100)

    @field_validator("default_timezone")
    @classmethod
    def timezone_must_be_known(cls, value: str) -> str:
        return _validate_timezone(value)


class ProjectCreate(ProjectBase):
    client_id: int


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    is_active: bool | None = None
    default_check_interval: CheckInterval | None = None
    default_execution_time: time | None = None
    default_timezone: str | None = None
    rank_drop_threshold: int | None = Field(default=None, ge=1, le=50)
    dataforseo_depth: int | None = Field(default=None, ge=10, le=100)

    @field_validator("default_timezone")
    @classmethod
    def timezone_must_be_known(cls, value: str | None) -> str | None:
        return None if value is None else _validate_timezone(value)


class ProjectScheduleUpdate(BaseModel):
    """Body of the project-level cron form.

    ``apply_to_all_urls`` forces every URL in the project back to inheriting,
    overriding any per-URL schedule. It defaults to False because silently
    discarding deliberately staggered times would be destructive.
    """

    default_check_interval: CheckInterval
    default_execution_time: time
    default_timezone: str = "UTC"
    rank_drop_threshold: int = Field(default=3, ge=1, le=50)
    dataforseo_depth: int = Field(default=10, ge=10, le=100)
    apply_to_all_urls: bool = False

    @field_validator("default_timezone")
    @classmethod
    def timezone_must_be_known(cls, value: str) -> str:
        return _validate_timezone(value)


class ProjectScheduleResponse(BaseModel):
    project_id: int
    default_check_interval: CheckInterval
    default_execution_time: time
    default_timezone: str
    rank_drop_threshold: int = 3
    dataforseo_depth: int = 10
    inheriting_url_count: int
    overriding_url_count: int


class ProjectResponse(ORMModel):
    id: int
    client_id: int
    name: str
    description: str | None
    is_active: bool
    default_check_interval: CheckInterval
    default_execution_time: time
    default_timezone: str
    rank_drop_threshold: int = 3
    dataforseo_depth: int = 10
    created_at: datetime
    updated_at: datetime


class ProjectWithStats(ProjectResponse):
    client_name: str | None = None
    url_count: int = 0
    active_url_count: int = 0
    inheriting_url_count: int = 0
